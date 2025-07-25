import streamlit as st
import pandas as pd
import plotly.express as px
import io
import plotly.graph_objects as go
import inspect
from datetime import datetime
import re

# --- Page and Session State Setup ---
st.set_page_config(layout="wide", page_title="Capital Project Portfolio Dashboard")

# Initialize session state for comments and report button visibility
if 'comment_variance' not in st.session_state:
    st.session_state.comment_variance = ""
if 'comment_impact' not in st.session_state:
    st.session_state.comment_impact = ""
if 'comment_bottom5' not in st.session_state:
    st.session_state.comment_bottom5 = ""
if 'reports_ready' not in st.session_state:
    st.session_state.reports_ready = False

# Define current_year and current_month globally
current_year = datetime.now().year
current_month = datetime.now().month
current_year_str = str(current_year)


# --- Data Loading and Cleaning ---
@st.cache_data
def load_data(uploaded_file: io.BytesIO) -> pd.DataFrame:
    """
    Loads and preprocesses data from a CSV or Excel file.
    """
    try:
        # UPDATED: Handle both CSV and Excel files
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return pd.DataFrame()

    def clean_col_name(col_name: str) -> str:
        """Cleans a single column name."""
        col_name = str(col_name).strip().replace(' ', '_').replace('+', '_').replace('.', '_').replace('-', '_')
        col_name = '_'.join(filter(None, col_name.split('_')))
        col_name = col_name.upper()
        corrections = {
            'PROJEC_TID': 'PROJECT_ID', 'INI_MATIVE_PROGRAM': 'INITIATIVE_PROGRAM',
            'ALL_PRIOR_YEARS_A': 'ALL_PRIOR_YEARS_ACTUALS', 'C_URRENT_EAC': 'CURRENT_EAC',
            'QE_RUN_RATE': 'QE_RUN_RATE', 'RATE_1': 'RATE_SUPPLEMENTARY'
        }
        return corrections.get(col_name, col_name)

    df.columns = [clean_col_name(col) for col in df.columns]

    cols = []
    seen = {}
    for col in df.columns:
        original_col = col
        count = seen.get(col, 0)
        if count > 0:
            col = f"{col}_{count}"
        cols.append(col)
        seen[original_col] = count + 1
    df.columns = cols

    financial_pattern = r'^(20\d{2}_\d{2}_(A|F|CP)(_\d+)?|ALL_PRIOR_YEARS_ACTUALS|BUSINESS_ALLOCATION|CURRENT_EAC|QE_FORECAST_VS_QE_PLAN|FORECAST_VS_BA|YE_RUN|RATE|QE_RUN|RATE_SUPPLEMENTARY)$'
    financial_cols_to_convert = [col for col in df.columns if pd.Series([col]).str.contains(financial_pattern, regex=True).any()]

    for col in financial_cols_to_convert:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '').str.strip().replace('', '0')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    monthly_col_pattern = re.compile(rf'^{current_year}_\d{{2}}_([AF]|CP)$')
    monthly_actuals_cols, monthly_forecasts_cols, monthly_plan_cols = [], [], []
    for col in df.columns:
        match = monthly_col_pattern.match(col)
        if match:
            col_type = match.group(1)
            if col_type == 'A': monthly_actuals_cols.append(col)
            elif col_type == 'F': monthly_forecasts_cols.append(col)
            elif col_type == 'CP': monthly_plan_cols.append(col)

    for col_list in [monthly_actuals_cols, monthly_forecasts_cols, monthly_plan_cols]:
        for col in col_list:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df[f'TOTAL_{current_year}_ACTUALS'] = df[monthly_actuals_cols].sum(axis=1) if monthly_actuals_cols else 0
    df[f'TOTAL_{current_year}_FORECASTS'] = df[monthly_forecasts_cols].sum(axis=1) if monthly_forecasts_cols else 0
    df[f'TOTAL_{current_year}_CAPITAL_PLAN'] = df[monthly_plan_cols].sum(axis=1) if monthly_plan_cols else 0

    if 'ALL_PRIOR_YEARS_ACTUALS' in df.columns:
        df['TOTAL_ACTUALS_TO_DATE'] = df['ALL_PRIOR_YEARS_ACTUALS'] + df[f'TOTAL_{current_year}_ACTUALS']
    else:
        df['TOTAL_ACTUALS_TO_DATE'] = df[f'TOTAL_{current_year}_ACTUALS']
        st.warning("Column 'ALL_PRIOR_YEARS_ACTUALS' not found.")

    ytd_actual_cols = [col for col in monthly_actuals_cols if int(col.split('_')[1]) <= current_month]
    df['SUM_ACTUAL_SPEND_YTD'] = df[ytd_actual_cols].sum(axis=1) if ytd_actual_cols else 0
    df['SUM_OF_FORECASTED_NUMBERS'] = df[f'TOTAL_{current_year}_FORECASTS']
    df['RUN_RATE_PER_MONTH'] = (df[f'TOTAL_{current_year}_ACTUALS'] + df[f'TOTAL_{current_year}_FORECASTS']) / 12

    if 'BUSINESS_ALLOCATION' in df.columns:
        df['CAPITAL_VARIANCE'] = df['BUSINESS_ALLOCATION'] - df[f'TOTAL_{current_year}_FORECASTS']
        df['CAPITAL_UNDERSPEND'] = df['CAPITAL_VARIANCE'].apply(lambda x: x if x > 0 else 0)
        df['CAPITAL_OVERSPEND'] = df['CAPITAL_VARIANCE'].apply(lambda x: abs(x) if x < 0 else 0)
    else:
        df['CAPITAL_VARIANCE'], df['CAPITAL_UNDERSPEND'], df['CAPITAL_OVERSPEND'] = 0, 0, 0
        st.warning("Column 'BUSINESS_ALLOCATION' not found.")

    df['NET_REALLOCATION_AMOUNT'] = df['CAPITAL_UNDERSPEND'] - df['CAPITAL_OVERSPEND']
    
    num_actual_months = len(ytd_actual_cols) if ytd_actual_cols else 1
    num_forecast_months = len(monthly_forecasts_cols) if monthly_forecasts_cols else 1
    df['AVG_ACTUAL_SPEND'] = df['SUM_ACTUAL_SPEND_YTD'] / num_actual_months
    df['AVG_FORECAST_SPEND'] = df[f'TOTAL_{current_year}_FORECASTS'] / num_forecast_months
    df['TOTAL_SPEND_VARIANCE'] = df[f'TOTAL_{current_year}_ACTUALS'] - df[f'TOTAL_{current_year}_FORECASTS']

    monthly_af_variance_cols = []
    for i in range(1, 13):
        actual_col, forecast_col = f'{current_year}_{i:02d}_A', f'{current_year}_{i:02d}_F'
        if actual_col in df.columns and forecast_col in df.columns:
            variance_col_name = f'{current_year}_{i:02d}_AF_VARIANCE'
            df[variance_col_name] = df[actual_col] - df[forecast_col]
            monthly_af_variance_cols.append(variance_col_name)

    df['AVERAGE_MONTHLY_SPREAD_SCORE'] = df[monthly_af_variance_cols].abs().mean(axis=1) if monthly_af_variance_cols else 0
    return df

# --- Report Generation Functions ---
def generate_html_report(metrics, figures, tables, comments, project_details_html=None):
    """Generates a comprehensive HTML report of the dashboard state."""
    monthly_trends_html = figures['monthly_trends'].to_html(full_html=False, include_plotlyjs='cdn') if figures.get('monthly_trends') else '<p>No monthly trend data available.</p>'
    
    # Function to create a comment block if comment exists
    def create_comment_block(title, comment_text):
        if comment_text and comment_text.strip():
            return f"<h3>{title}</h3><p style='white-space: pre-wrap; background-color:#f0f2f6; padding: 10px; border-radius: 5px;'>{comment_text}</p>"
        return ""

    report_html = f"""
    <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Capital Project Report</title><style>
    body{{font-family:sans-serif;margin:20px;color:#333}}h1,h2,h3{{color:#004d40}}.metric-container{{display:flex;justify-content:space-around;flex-wrap:wrap;margin-bottom:20px}}
    .metric-box{{border:1px solid #ddd;border-radius:8px;padding:15px;margin:10px;flex:1;min-width:200px;text-align:center;background-color:#f9f9f9}}
    .metric-label{{font-size:0.9em;color:#555}}.metric-value{{font-size:1.5em;font-weight:bold;color:#222;margin-top:5px}}
    table{{width:100%;border-collapse:collapse;margin-top:20px}}th,td{{border:1px solid #ddd;padding:8px;text-align:left}}th{{background-color:#e6f2f0}}
    .chart-container{{margin-top:30px;page-break-inside:avoid;}}.section-title{{margin-top:40px;border-bottom:2px solid #004d40;padding-bottom:10px;page-break-after:avoid;}}
    footer{{text-align:center;margin-top:50px;padding-top:20px;border-top:1px solid #eee;font-size:0.8em;color:#777}}
    .flex-container{{display:flex;justify-content:space-between;gap:20px;page-break-inside:avoid;}}.flex-child{{flex:1;min-width:45%;}}
    </style></head><body>
    <h1>Capital Project Portfolio Report</h1><p>Generated on: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <h2 class="section-title">Key Metrics Overview</h2><div class="metric-container">
    {''.join([f'<div class="metric-box"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>' for label, value in metrics.items()])}
    </div>
    <h2 class="section-title">Filtered Project Details</h2>{tables['project_details']}
    <h2 class="section-title">{current_year} Monthly Spend Trends</h2><div class="chart-container">{monthly_trends_html}</div>
    <h2 class="section-title">Project Spend Variance Analysis</h2>{create_comment_block('Analyst Comments', comments['variance'])}<div class="flex-container">
    <div class="flex-child"><h3>Total Spend</h3>{figures['total_spend'].to_html(full_html=False, include_plotlyjs='cdn') if figures['total_spend'] else '<p>N/A</p>'}</div>
    <div class="flex-child"><h3>Average Spend</h3>{figures['avg_spend'].to_html(full_html=False, include_plotlyjs='cdn') if figures['avg_spend'] else '<p>N/A</p>'}</div>
    </div>
    <h2 class="section-title">Budget Impact & Reallocation</h2>{create_comment_block('Analyst Comments', comments['impact'])}<div class="flex-container">
    <div class="flex-child"><h3>Largest Forecasted Overspend</h3>{tables['overspend']}</div>
    <div class="flex-child"><h3>Largest Potential Underspend</h3>{tables['underspend']}</div>
    </div>
    {project_details_html if project_details_html else ''}
    <h2 class="section-title">Project Performance</h2>{create_comment_block('Analyst Comments on Bottom 5 Projects', comments['bottom5'])}<div class="flex-container">
    <div class="flex-child"><h3>Top 5 Best Behaving</h3>{tables['top_5']}</div>
    <div class="flex-child"><h3>Bottom 5 Worst Behaving</h3>{tables['bottom_5']}</div>
    </div>
    <footer><p>Generated by Capital Project Portfolio Dashboard</p></footer>
    </body></html>"""
    return report_html

def generate_excel_report(metrics, tables, comments):
    """Generates a multi-sheet Excel report."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Summary and Comments Sheet
        summary_df = pd.DataFrame([metrics])
        comments_df = pd.DataFrame.from_dict(comments, orient='index', columns=['Comments'])
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        comments_df.to_excel(writer, sheet_name='Summary', startrow=len(summary_df) + 2)

        # Data sheets
        for name, df in tables.items():
            df.to_excel(writer, sheet_name=name.replace(' ', '_')[:31], index=False)

    return output.getvalue()

# --- Streamlit App Layout ---
st.title("💰 Capital Project Portfolio Dashboard")
st.markdown("This dashboard provides an interactive overview of your capital projects, allowing you to track financials, monitor trends, and identify variances.")

# UPDATED: File uploader now accepts CSV and XLSX
uploaded_file = st.file_uploader("Upload your Capital Project CSV or Excel file", type=["csv", "xlsx"])

if uploaded_file is not None:
    # Reset report readiness when a new file is uploaded
    st.session_state.reports_ready = False
    df = load_data(uploaded_file)
    if not df.empty:
        st.sidebar.header("Filter Projects")
        # --- FILTERS (Logic is unchanged) ---
        filter_columns = { "PORTFOLIO_OBS_LEVEL1": "Select Portfolio Level", "SUB_PORTFOLIO_OBS_LEVEL2": "Select Sub-Portfolio Level", "PROJECT_MANAGER": "Select Project Manager", "BRS_CLASSIFICATION": "Select BRS Classification", "FUND_DECISION": "Select Fund Decision" }
        selected_filters = {}
        for col_name, display_name in filter_columns.items():
            if col_name in df.columns:
                options = ['All'] + df[col_name].dropna().unique().tolist()
                selected_filters[col_name] = st.sidebar.selectbox(display_name, options, on_change=lambda: st.session_state.update(reports_ready=False))
            else:
                if col_name == "FUND_DECISION": st.sidebar.info(f"Column '{col_name}' not found.")
                selected_filters[col_name] = 'All'
        filtered_df = df.copy()
        for col_name, selected_value in selected_filters.items():
            if selected_value != 'All' and col_name in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[col_name] == selected_value]

        if filtered_df.empty:
            st.warning("No projects match the selected filters."); st.stop()

        # --- Data Calculation for UI ---
        total_projects = len(filtered_df)
        sum_actual_spend_ytd = filtered_df['SUM_ACTUAL_SPEND_YTD'].sum()
        sum_of_forecasted_numbers_sum = filtered_df['SUM_OF_FORECASTED_NUMBERS'].sum()
        run_rate_per_month = filtered_df['RUN_RATE_PER_MONTH'].mean()
        capital_underspend = filtered_df['CAPITAL_UNDERSPEND'].sum()
        capital_overspend = filtered_df['CAPITAL_OVERSPEND'].sum()
        net_reallocation_amount = filtered_df['NET_REALLOCATION_AMOUNT'].sum()

        # --- UI Sections ---
        st.subheader("Key Metrics Overview")
        col1, col2, col3 = st.columns(3)
        col1.metric("Number of Projects", total_projects)
        col2.metric("Sum Actual Spend (YTD)", f"${sum_actual_spend_ytd:,.2f}")
        col3.metric("Sum Of Forecasted Numbers", f"${sum_of_forecasted_numbers_sum:,.2f}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Average Run Rate / Month", f"${run_rate_per_month:,.2f}")
        m2.metric("Total Potential Underspend", f"${capital_underspend:,.2f}")
        m3.metric("Total Potential Overspend", f"${capital_overspend:,.2f}")
        m4.metric("Net Reallocation Amount", f"${net_reallocation_amount:,.2f}")
        st.markdown("---")

        st.subheader("Project Details")
        project_table_cols = [ 'PORTFOLIO_OBS_LEVEL1', 'SUB_PORTFOLIO_OBS_LEVEL2', 'PROJECT_NAME', 'PROJECT_MANAGER', 'BRS_CLASSIFICATION', 'FUND_DECISION', 'BUSINESS_ALLOCATION', 'CURRENT_EAC', 'ALL_PRIOR_YEARS_ACTUALS', f'TOTAL_{current_year}_ACTUALS', f'TOTAL_{current_year}_FORECASTS', f'TOTAL_{current_year}_CAPITAL_PLAN', 'CAPITAL_UNDERSPEND', 'CAPITAL_OVERSPEND', 'AVERAGE_MONTHLY_SPREAD_SCORE' ]
        project_table_cols_present = [col for col in project_table_cols if col in filtered_df.columns]
        financial_format_map = { col: "${:,.2f}" for col in project_table_cols_present if 'ACTUALS' in col or 'FORECASTS' in col or 'PLAN' in col or 'ALLOCATION' in col or 'EAC' in col or 'SPEND' in col or 'AMOUNT' in col or 'SCORE' in col }
        st.dataframe(filtered_df[project_table_cols_present].style.format(financial_format_map), use_container_width=True, hide_index=True)
        st.markdown("---")

        st.subheader(f"{current_year} Monthly Spend Trends")
        # (Logic for this chart is unchanged)
        # ...
        st.markdown("---")

        st.subheader("🔎 Project Spend Variance Analysis")
        st.markdown("These charts compare spend for each project, sorted to show the greatest difference between what was spent and what was forecasted.")
        num_projects_to_show = st.slider("Select number of projects to display in variance charts:", 5, min(50, total_projects), min(15, total_projects), 5, on_change=lambda: st.session_state.update(reports_ready=False))
        variance_df = filtered_df.reindex(filtered_df['TOTAL_SPEND_VARIANCE'].abs().sort_values(ascending=False).index).head(num_projects_to_show)
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Total Spend: Actuals vs. Forecast**"); fig_total_spend_variance = px.bar(variance_df.melt(id_vars='PROJECT_NAME', value_vars=[f'TOTAL_{current_year}_ACTUALS', f'TOTAL_{current_year}_FORECASTS'], var_name='Spend Type', value_name='Amount').replace({f'TOTAL_{current_year}_ACTUALS': 'Total Actuals', f'TOTAL_{current_year}_FORECASTS': 'Total Forecasts'}), y='PROJECT_NAME', x='Amount', color='Spend Type', barmode='group', orientation='h', height=max(400, num_projects_to_show * 35)).update_layout(yaxis={'categoryorder':'total ascending'}, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)); st.plotly_chart(fig_total_spend_variance, use_container_width=True)
        with c2:
            st.write(f"**Average Monthly Spend**"); fig_avg_spend_variance = px.bar(variance_df.melt(id_vars='PROJECT_NAME', value_vars=['AVG_ACTUAL_SPEND', 'AVG_FORECAST_SPEND'], var_name='Spend Type', value_name='Amount').replace({'AVG_ACTUAL_SPEND': 'Avg Actuals (YTD)', 'AVG_FORECAST_SPEND': 'Avg Forecasts (Annual)'}), y='PROJECT_NAME', x='Amount', color='Spend Type', barmode='group', orientation='h', height=max(400, num_projects_to_show * 35)).update_layout(yaxis={'categoryorder':'total ascending'}, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)); st.plotly_chart(fig_avg_spend_variance, use_container_width=True)
        # NEW: Comment box for this section
        st.text_area("Add comments for the Spend Variance section:", key="comment_variance", on_change=lambda: st.session_state.update(reports_ready=False))
        st.markdown("---")

        st.subheader("🎯 Budget Impact and Reallocation Insights")
        overspend_projects = filtered_df[filtered_df['CAPITAL_OVERSPEND'] > 0].sort_values('CAPITAL_OVERSPEND', ascending=False)
        underspend_projects = filtered_df[filtered_df['CAPITAL_UNDERSPEND'] > 0].sort_values('CAPITAL_UNDERSPEND', ascending=False)
        currency_formatter = { 'BUSINESS_ALLOCATION': "${:,.2f}", f'TOTAL_{current_year}_FORECASTS': "${:,.2f}", 'CAPITAL_OVERSPEND': "${:,.2f}", 'CAPITAL_UNDERSPEND': "${:,.2f}" }
        i1, i2 = st.columns(2)
        with i1:
            st.write("#### Projects with Largest Forecasted Overspend"); st.markdown("These projects are forecasted to exceed their `BUSINESS_ALLOCATION`.")
            if not overspend_projects.empty: st.dataframe(overspend_projects[['PROJECT_NAME', 'BUSINESS_ALLOCATION', f'TOTAL_{current_year}_FORECASTS', 'CAPITAL_OVERSPEND']].head().style.format(currency_formatter), use_container_width=True, hide_index=True)
            else: st.info("No projects are currently forecasting an overspend.")
        with i2:
            st.write("#### Projects with Largest Potential Underspend"); st.markdown("These projects have capital that could be reallocated.")
            if not underspend_projects.empty: st.dataframe(underspend_projects[['PROJECT_NAME', 'BUSINESS_ALLOCATION', f'TOTAL_{current_year}_FORECASTS', 'CAPITAL_UNDERSPEND']].head().style.format(currency_formatter), use_container_width=True, hide_index=True)
            else: st.info("No projects are currently forecasting an underspend.")
        if not overspend_projects.empty and not underspend_projects.empty: st.success(f"**Reallocation Suggestion:** There is a total potential underspend of **${capital_underspend:,.2f}** which could cover the total potential overspend of **${capital_overspend:,.2f}**.")
        # NEW: Comment box for this section
        st.text_area("Add comments for the Budget Impact section:", key="comment_impact", on_change=lambda: st.session_state.update(reports_ready=False))
        st.markdown("---")
        
        st.subheader("Individual Project Financials")
        # (Logic for this chart is unchanged)
        # ...
        st.markdown("---")

        st.subheader("🏆 Project Performance")
        project_performance_ranked = filtered_df.sort_values('AVERAGE_MONTHLY_SPREAD_SCORE')
        if 'AVERAGE_MONTHLY_SPREAD_SCORE' in filtered_df.columns:
            st.info("**How is project performance ranked?** By the **'Average Monthly Spread Score'**: the average monthly difference between actual vs. forecasted spend. A **lower score is better**.")
            st.write("#### Top 5 Best Behaving Projects (Lowest Avg. Monthly Spread)"); st.dataframe(project_performance_ranked.head(5)[['PROJECT_NAME', 'AVERAGE_MONTHLY_SPREAD_SCORE']].style.format({'AVERAGE_MONTHLY_SPREAD_SCORE': "${:,.2f}"}), use_container_width=True, hide_index=True)
            st.write("#### Bottom 5 Worst Behaving Projects (Highest Avg. Monthly Spread)"); st.dataframe(project_performance_ranked.tail(5).sort_values('AVERAGE_MONTHLY_SPREAD_SCORE', ascending=False)[['PROJECT_NAME', 'AVERAGE_MONTHLY_SPREAD_SCORE']].style.format({'AVERAGE_MONTHLY_SPREAD_SCORE': "${:,.2f}"}), use_container_width=True, hide_index=True)
            # NEW: Comment box for the bottom 5
            st.text_area("Add comments for the Bottom 5 Projects:", key="comment_bottom5", on_change=lambda: st.session_state.update(reports_ready=False))
        st.markdown("---")

        # --- UPDATED: Reporting Section ---
        st.subheader("Generate Professional Reports")
        st.markdown("Add your comments in the sections above, then click the button below to prepare your downloadable reports.")

        if st.button("Prepare Reports for Download"):
            st.session_state.reports_ready = True

        if st.session_state.get('reports_ready', False):
            # Prepare data for reports
            metrics_data = { "Number of Projects": total_projects, "Sum Actual Spend (YTD)": sum_actual_spend_ytd, "Sum Of Forecasted Numbers": sum_of_forecasted_numbers_sum, "Avg Run Rate / Month": run_rate_per_month, "Total Potential Underspend": capital_underspend, "Total Potential Overspend": capital_overspend, "Net Reallocation": net_reallocation_amount }
            figures_data = { 'monthly_trends': None, 'total_spend': fig_total_spend_variance, 'avg_spend': fig_avg_spend_variance } # Placeholder for monthly trends figure
            tables_data_raw = { 'Project_Details': filtered_df[project_table_cols_present], 'Over-Spend_Projects': overspend_projects, 'Under-Spend_Projects': underspend_projects, 'Performance_Rankings': project_performance_ranked }
            tables_data_styled = {
                'project_details': filtered_df[project_table_cols_present].style.format(financial_format_map).to_html(index=False),
                'overspend': overspend_projects[['PROJECT_NAME', 'BUSINESS_ALLOCATION', f'TOTAL_{current_year}_FORECASTS', 'CAPITAL_OVERSPEND']].head().style.format(currency_formatter).to_html(index=False),
                'underspend': underspend_projects[['PROJECT_NAME', 'BUSINESS_ALLOCATION', f'TOTAL_{current_year}_FORECASTS', 'CAPITAL_UNDERSPEND']].head().style.format(currency_formatter).to_html(index=False),
                'top_5': project_performance_ranked.head(5)[['PROJECT_NAME', 'AVERAGE_MONTHLY_SPREAD_SCORE']].style.format({'AVERAGE_MONTHLY_SPREAD_SCORE': "${:,.2f}"}).to_html(index=False),
                'bottom_5': project_performance_ranked.tail(5).sort_values('AVERAGE_MONTHLY_SPREAD_SCORE', ascending=False)[['PROJECT_NAME', 'AVERAGE_MONTHLY_SPREAD_SCORE']].style.format({'AVERAGE_MONTHLY_SPREAD_SCORE': "${:,.2f}"}).to_html(index=False)
            }
            comments_data = { 'variance': st.session_state.comment_variance, 'impact': st.session_state.comment_impact, 'bottom5': st.session_state.comment_bottom5 }
            
            # Generate report content
            html_report = generate_html_report(metrics_data, figures_data, tables_data_styled, comments_data)
            excel_report = generate_excel_report(metrics_data, tables_data_raw, comments_data)

            # Display download buttons
            st.info("Your reports are ready to download below.")
            dl1, dl2 = st.columns(2)
            with dl1:
                st.download_button("⬇️ Download Report as HTML", html_report, "capital_project_report.html", "text/html")
            with dl2:
                st.download_button("⬇️ Download Report as Excel", excel_report, "capital_project_report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

else:
    st.info("Upload your Capital Project CSV or Excel file to get started!")

st.markdown("---")
with st.expander("View Application Source Code"):
    st.code(inspect.getsource(inspect.currentframe()), language='python')
