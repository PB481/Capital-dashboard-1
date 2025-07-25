import streamlit as st
import pandas as pd
import plotly.express as px
import io
import plotly.graph_objects as go
import inspect
from datetime import datetime
import re

# Define current_year and current_month globally
current_year = datetime.now().year
current_month = datetime.now().month
current_year_str = str(current_year)

# Set page configuration for a wider layout
st.set_page_config(layout="wide", page_title="Capital Project Portfolio Dashboard")

# --- Data Loading and Cleaning ---
@st.cache_data
def load_data(uploaded_file: io.BytesIO) -> pd.DataFrame:
    """
    Loads and preprocesses the CSV data for the Capital Project Portfolio Dashboard.
    """
    try:
        df = pd.read_csv(uploaded_file)
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

# --- Streamlit App Layout ---
st.title("💰 Capital Project Portfolio Dashboard")
st.markdown("This dashboard provides an interactive overview of your capital projects, allowing you to track financials, monitor trends, and identify variances.")

uploaded_file = st.file_uploader("Upload your Capital Project CSV file", type=["csv"])

if uploaded_file is not None:
    df = load_data(uploaded_file)
    if not df.empty:
        st.sidebar.header("Filter Projects")
        filter_columns = {
            "PORTFOLIO_OBS_LEVEL1": "Select Portfolio Level", "SUB_PORTFOLIO_OBS_LEVEL2": "Select Sub-Portfolio Level",
            "PROJECT_MANAGER": "Select Project Manager", "BRS_CLASSIFICATION": "Select BRS Classification",
            "FUND_DECISION": "Select Fund Decision"
        }
        selected_filters = {}
        for col_name, display_name in filter_columns.items():
            if col_name in df.columns:
                options = ['All'] + df[col_name].dropna().unique().tolist()
                selected_filters[col_name] = st.sidebar.selectbox(display_name, options)
            else:
                if col_name == "FUND_DECISION": st.sidebar.info(f"Column '{col_name}' not found.")
                selected_filters[col_name] = 'All'

        filtered_df = df.copy()
        for col_name, selected_value in selected_filters.items():
            if selected_value != 'All' and col_name in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[col_name] == selected_value]

        if filtered_df.empty:
            st.warning("No projects match the selected filters. Please adjust your selections.")
            st.stop()

        st.subheader("Key Metrics Overview")
        total_projects = len(filtered_df)
        sum_actual_spend_ytd = filtered_df['SUM_ACTUAL_SPEND_YTD'].sum()
        sum_of_forecasted_numbers_sum = filtered_df['SUM_OF_FORECASTED_NUMBERS'].sum()
        run_rate_per_month = filtered_df['RUN_RATE_PER_MONTH'].mean()
        capital_underspend = filtered_df['CAPITAL_UNDERSPEND'].sum()
        capital_overspend = filtered_df['CAPITAL_OVERSPEND'].sum()
        net_reallocation_amount = filtered_df['NET_REALLOCATION_AMOUNT'].sum()

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
        project_table_cols = [
            'PORTFOLIO_OBS_LEVEL1', 'SUB_PORTFOLIO_OBS_LEVEL2', 'PROJECT_NAME', 'PROJECT_MANAGER', 
            'BRS_CLASSIFICATION', 'FUND_DECISION', 'BUSINESS_ALLOCATION', 'CURRENT_EAC', 'ALL_PRIOR_YEARS_ACTUALS',
            f'TOTAL_{current_year}_ACTUALS', f'TOTAL_{current_year}_FORECASTS', f'TOTAL_{current_year}_CAPITAL_PLAN',
            'CAPITAL_UNDERSPEND', 'CAPITAL_OVERSPEND', 'AVERAGE_MONTHLY_SPREAD_SCORE'
        ]
        project_table_cols_present = [col for col in project_table_cols if col in filtered_df.columns]
        financial_format_map = { col: "${:,.2f}" for col in project_table_cols_present if 'ACTUALS' in col or 'FORECASTS' in col or 'PLAN' in col or 'ALLOCATION' in col or 'EAC' in col or 'SPEND' in col or 'AMOUNT' in col or 'SCORE' in col }
        st.dataframe(filtered_df[project_table_cols_present].style.format(financial_format_map), use_container_width=True, hide_index=True)
        st.markdown("---")

        st.subheader("🔎 Project Spend Variance Analysis")
        st.markdown("These charts compare spend for each project, sorted to show the greatest difference between what was spent and what was forecasted.")
        num_projects_to_show = st.slider("Select number of projects to display in variance charts:", 5, min(50, total_projects), min(15, total_projects), 5)
        
        variance_df = filtered_df.reindex(filtered_df['TOTAL_SPEND_VARIANCE'].abs().sort_values(ascending=False).index).head(num_projects_to_show)
        
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Total Spend: Actuals vs. Forecast**")
            total_spend_chart_df = variance_df[['PROJECT_NAME', f'TOTAL_{current_year}_ACTUALS', f'TOTAL_{current_year}_FORECASTS']].melt(id_vars='PROJECT_NAME', var_name='Spend Type', value_name='Amount')
            total_spend_chart_df['Spend Type'] = total_spend_chart_df['Spend Type'].replace({f'TOTAL_{current_year}_ACTUALS': 'Total Actuals', f'TOTAL_{current_year}_FORECASTS': 'Total Forecasts'})
            fig_total_spend_variance = px.bar(total_spend_chart_df, y='PROJECT_NAME', x='Amount', color='Spend Type', barmode='group', orientation='h', height=max(400, num_projects_to_show * 35))
            fig_total_spend_variance.update_layout(yaxis={'categoryorder':'total ascending'}, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_total_spend_variance, use_container_width=True)

        with c2:
            st.write(f"**Average Monthly Spend**")
            avg_spend_chart_df = variance_df[['PROJECT_NAME', 'AVG_ACTUAL_SPEND', 'AVG_FORECAST_SPEND']].melt(id_vars='PROJECT_NAME', var_name='Spend Type', value_name='Amount')
            avg_spend_chart_df['Spend Type'] = avg_spend_chart_df['Spend Type'].replace({'AVG_ACTUAL_SPEND': 'Avg Actuals (YTD)', 'AVG_FORECAST_SPEND': 'Avg Forecasts (Annual)'})
            fig_avg_spend_variance = px.bar(avg_spend_chart_df, y='PROJECT_NAME', x='Amount', color='Spend Type', barmode='group', orientation='h', height=max(400, num_projects_to_show * 35))
            fig_avg_spend_variance.update_layout(yaxis={'categoryorder':'total ascending'}, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_avg_spend_variance, use_container_width=True)
        st.markdown("---")

        st.subheader("🎯 Budget Impact and Reallocation Insights")
        overspend_projects = filtered_df[filtered_df['CAPITAL_OVERSPEND'] > 0].sort_values('CAPITAL_OVERSPEND', ascending=False)
        underspend_projects = filtered_df[filtered_df['CAPITAL_UNDERSPEND'] > 0].sort_values('CAPITAL_UNDERSPEND', ascending=False)
        
        # --- BUG FIX STARTS HERE ---
        # Define a formatter dictionary for the currency columns only
        currency_formatter = {
            'BUSINESS_ALLOCATION': "${:,.2f}",
            f'TOTAL_{current_year}_FORECASTS': "${:,.2f}",
            'CAPITAL_OVERSPEND': "${:,.2f}",
            'CAPITAL_UNDERSPEND': "${:,.2f}"
        }

        i1, i2 = st.columns(2)
        with i1:
            st.write("#### Projects with Largest Forecasted Overspend")
            st.markdown("These projects are forecasted to exceed their `BUSINESS_ALLOCATION`.")
            if not overspend_projects.empty:
                # Apply the specific formatter, not a generic one
                st.dataframe(overspend_projects[['PROJECT_NAME', 'BUSINESS_ALLOCATION', f'TOTAL_{current_year}_FORECASTS', 'CAPITAL_OVERSPEND']].head().style.format(currency_formatter), use_container_width=True, hide_index=True)
            else: 
                st.info("No projects are currently forecasting an overspend.")
        with i2:
            st.write("#### Projects with Largest Potential Underspend")
            st.markdown("These projects have capital that could be reallocated.")
            if not underspend_projects.empty:
                # Apply the specific formatter here as well
                st.dataframe(underspend_projects[['PROJECT_NAME', 'BUSINESS_ALLOCATION', f'TOTAL_{current_year}_FORECASTS', 'CAPITAL_UNDERSPEND']].head().style.format(currency_formatter), use_container_width=True, hide_index=True)
            else: 
                st.info("No projects are currently forecasting an underspend.")
        # --- BUG FIX ENDS HERE ---
        
        if not overspend_projects.empty and not underspend_projects.empty:
             st.success(f"**Reallocation Suggestion:** There is a total potential underspend of **${capital_underspend:,.2f}** which could cover the total potential overspend of **${capital_overspend:,.2f}**.")
        st.markdown("---")
        
        st.subheader("Individual Project Financials")
        project_names = ['Select a Project'] + filtered_df['PROJECT_NAME'].dropna().unique().tolist()
        selected_project_name = st.selectbox("Select a project for a detailed monthly view:", project_names)

        if selected_project_name != 'Select a Project':
            project_details = filtered_df[filtered_df['PROJECT_NAME'] == selected_project_name].iloc[0]
            st.write(f"### Details for: {project_details['PROJECT_NAME']}")

            d1, d2, d3 = st.columns(3)
            d1.metric("Business Allocation", f"${project_details.get('BUSINESS_ALLOCATION', 0):,.2f}")
            d2.metric("Current EAC", f"${project_details.get('CURRENT_EAC', 0):,.2f}")
            d3.metric("All Prior Years Actuals", f"${project_details.get('ALL_PRIOR_YEARS_ACTUALS', 0):,.2f}")
            
            st.write(f"#### {current_year_str} Monthly Breakdown:")
            monthly_breakdown_data = {'Month': [f"{current_year_str}_{i:02d}" for i in range(1, 13)]}
            monthly_types = {'_A': 'Actuals', '_F': 'Forecasts', '_CP': 'Capital Plan'}
            for suffix, name in monthly_types.items():
                monthly_values = [project_details.get(f'{current_year_str}_{i:02d}{suffix}', 0) for i in range(1, 13)]
                monthly_breakdown_data[name] = monthly_values
            
            monthly_breakdown_df = pd.DataFrame(monthly_breakdown_data)
            st.dataframe(monthly_breakdown_df.style.format({'Actuals': "${:,.2f}", 'Forecasts': "${:,.2f}", 'Capital Plan': "${:,.2f}"}), use_container_width=True, hide_index=True)

            monthly_project_melted = monthly_breakdown_df.melt(id_vars=['Month'], var_name='Type', value_name='Amount')
            fig_project_monthly = px.bar(monthly_project_melted, x='Month', y='Amount', color='Type', barmode='group', title=f'Monthly Financials for {selected_project_name}')
            st.plotly_chart(fig_project_monthly, use_container_width=True)
        else:
            st.info("Select a project from the dropdown to see its detailed monthly financials.")
            project_details = None
            fig_project_monthly = None
        st.markdown("---")

        st.subheader("🏆 Project Performance")
        if 'AVERAGE_MONTHLY_SPREAD_SCORE' in filtered_df.columns:
            st.info("""
            **How is project performance ranked?**
            Performance is ranked by the **'Average Monthly Spread Score'**. This is the average of the absolute difference between a project's actual vs. forecasted spend for each month.
            A **lower score is better**, indicating a project's costs are tracking closely to its forecast.
            """)
            project_performance_ranked = filtered_df.sort_values('AVERAGE_MONTHLY_SPREAD_SCORE')
            st.write("#### Top 5 Best Behaving Projects (Lowest Avg. Monthly Spread)")
            st.dataframe(project_performance_ranked.head(5)[['PROJECT_NAME', 'AVERAGE_MONTHLY_SPREAD_SCORE']].style.format({'AVERAGE_MONTHLY_SPREAD_SCORE': "${:,.2f}"}), use_container_width=True, hide_index=True)
            st.write("#### Bottom 5 Worst Behaving Projects (Highest Avg. Monthly Spread)")
            st.dataframe(project_performance_ranked.tail(5).sort_values('AVERAGE_MONTHLY_SPREAD_SCORE', ascending=False)[['PROJECT_NAME', 'AVERAGE_MONTHLY_SPREAD_SCORE']].style.format({'AVERAGE_MONTHLY_SPREAD_SCORE': "${:,.2f}"}), use_container_width=True, hide_index=True)
        st.markdown("---")

        st.subheader("Generate Professional Report")
        st.markdown("Click the button below to generate and download a comprehensive HTML report of the current dashboard view.")

        def generate_html_report(metrics, figures, tables, project_details_html=None):
            """Generates a comprehensive HTML report of the dashboard state."""
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
            <h2 class="section-title">Project Spend Variance Analysis</h2><div class="flex-container">
            <div class="flex-child"><h3>Total Spend</h3>{figures['total_spend'].to_html(full_html=False, include_plotlyjs='cdn') if figures['total_spend'] else '<p>N/A</p>'}</div>
            <div class="flex-child"><h3>Average Spend</h3>{figures['avg_spend'].to_html(full_html=False, include_plotlyjs='cdn') if figures['avg_spend'] else '<p>N/A</p>'}</div>
            </div>
            <h2 class="section-title">Budget Impact & Reallocation</h2><div class="flex-container">
            <div class="flex-child"><h3>Largest Forecasted Overspend</h3>{tables['overspend']}</div>
            <div class="flex-child"><h3>Largest Potential Underspend</h3>{tables['underspend']}</div>
            </div>
            {project_details_html if project_details_html else ''}
            <h2 class="section-title">Project Performance</h2><div class="flex-container">
            <div class="flex-child"><h3>Top 5 Best Behaving</h3>{tables['top_5']}</div>
            <div class="flex-child"><h3>Bottom 5 Worst Behaving</h3>{tables['bottom_5']}</div>
            </div>
            <footer><p>Generated by Capital Project Portfolio Dashboard</p></footer>
            </body></html>"""
            return report_html

        if st.button("Generate Report (HTML)"):
            metrics_data = {
                "Number of Projects": total_projects, "Sum Actual Spend (YTD)": f"${sum_actual_spend_ytd:,.2f}",
                "Sum Of Forecasted Numbers": f"${sum_of_forecasted_numbers_sum:,.2f}", "Avg Run Rate / Month": f"${run_rate_per_month:,.2f}",
                "Total Potential Underspend": f"${capital_underspend:,.2f}", "Total Potential Overspend": f"${capital_overspend:,.2f}",
                "Net Reallocation": f"${net_reallocation_amount:,.2f}"
            }
            figures_data = {'total_spend': fig_total_spend_variance, 'avg_spend': fig_avg_spend_variance}
            
            # Use the corrected currency formatter for the report tables as well
            tables_data = {
                'project_details': filtered_df[project_table_cols_present].style.format(financial_format_map).to_html(index=False),
                'overspend': overspend_projects[['PROJECT_NAME', 'BUSINESS_ALLOCATION', f'TOTAL_{current_year}_FORECASTS', 'CAPITAL_OVERSPEND']].head().style.format(currency_formatter).to_html(index=False),
                'underspend': underspend_projects[['PROJECT_NAME', 'BUSINESS_ALLOCATION', f'TOTAL_{current_year}_FORECASTS', 'CAPITAL_UNDERSPEND']].head().style.format(currency_formatter).to_html(index=False),
                'top_5': project_performance_ranked.head(5)[['PROJECT_NAME', 'AVERAGE_MONTHLY_SPREAD_SCORE']].style.format({'AVERAGE_MONTHLY_SPREAD_SCORE': "${:,.2f}"}).to_html(index=False),
                'bottom_5': project_performance_ranked.tail(5).sort_values('AVERAGE_MONTHLY_SPREAD_SCORE', ascending=False)[['PROJECT_NAME', 'AVERAGE_MONTHLY_SPREAD_SCORE']].style.format({'AVERAGE_MONTHLY_SPREAD_SCORE': "${:,.2f}"}).to_html(index=False)
            }
            
            project_details_report_html = None
            if project_details is not None and fig_project_monthly is not None:
                project_metrics_html = f"""
                <div class="metric-container">
                    <div class="metric-box"><div class="metric-label">Business Allocation</div><div class="metric-value">${project_details.get('BUSINESS_ALLOCATION', 0):,.2f}</div></div>
                    <div class="metric-box"><div class="metric-label">Current EAC</div><div class="metric-value">${project_details.get('CURRENT_EAC', 0):,.2f}</div></div>
                    <div class="metric-box"><div class="metric-label">All Prior Years Actuals</div><div class="metric-value">${project_details.get('ALL_PRIOR_YEARS_ACTUALS', 0):,.2f}</div></div>
                </div>
                """
                project_table_html = monthly_breakdown_df.style.format({'Actuals': "${:,.2f}", 'Forecasts': "${:,.2f}", 'Capital Plan': "${:,.2f}"}).to_html(index=False)
                project_chart_html = fig_project_monthly.to_html(full_html=False, include_plotlyjs='cdn')
                project_details_report_html = f"""
                <h2 class="section-title">Detailed Financials for {selected_project_name}</h2>
                {project_metrics_html}
                <h3>{current_year_str} Monthly Breakdown</h3>
                {project_table_html}
                <div class="chart-container">{project_chart_html}</div>
                """

            report_content = generate_html_report(metrics_data, figures_data, tables_data, project_details_report_html)
            st.download_button("Download Report as HTML", report_content, "capital_project_report.html", "text/html")
else:
    st.info("Upload your Capital Project CSV file to get started!")

st.markdown("---")
with st.expander("View Application Source Code"):
    source_code = inspect.getsource(inspect.currentframe())
    st.code(source_code, language='python')
