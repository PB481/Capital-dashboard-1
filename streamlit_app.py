import streamlit as st
import pandas as pd
import plotly.express as px
import io
import plotly.graph_objects as go
import inspect
from datetime import datetime
import re # Import the re module for regular expressions

# Define current_year and current_month globally (important for broad accessibility)
current_year = datetime.now().year
current_month = datetime.now().month
current_year_str = str(current_year) # String version of year for f-strings

# Set page configuration for a wider layout
st.set_page_config(layout="wide", page_title="Capital Project Portfolio Dashboard")

# --- Data Loading and Cleaning ---
@st.cache_data
def load_data(uploaded_file: io.BytesIO) -> pd.DataFrame:
    """
    Loads and preprocesses the CSV data for the Capital Project Portfolio Dashboard.

    Args:
        uploaded_file (io.BytesIO): The uploaded CSV file.

    Returns:
        pd.DataFrame: A cleaned and preprocessed DataFrame, or an empty DataFrame if an error occurs.
    """
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return pd.DataFrame() # Return empty DataFrame on error

    # 1. Clean Column Names
    # A helper function to clean individual column names
    def clean_col_name(col_name: str) -> str:
        """Cleans a single column name."""
        col_name = str(col_name).strip().replace(' ', '_').replace('+', '_').replace('.', '_').replace('-', '_')
        col_name = '_'.join(filter(None, col_name.split('_')))
        col_name = col_name.upper()

        corrections = {
            'PROJEC_TID': 'PROJECT_ID',
            'INI_MATIVE_PROGRAM': 'INITIATIVE_PROGRAM',
            'ALL_PRIOR_YEARS_A': 'ALL_PRIOR_YEARS_ACTUALS',
            'C_URRENT_EAC': 'CURRENT_EAC',
            'QE_RUN_RATE': 'QE_RUN_RATE',
            'RATE_1': 'RATE_SUPPLEMENTARY'
        }
        return corrections.get(col_name, col_name)

    df.columns = [clean_col_name(col) for col in df.columns]

    # Handle duplicate column names
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

    # Identify financial columns
    financial_pattern = r'^(20\d{2}_\d{2}_(A|F|CP)(_\d+)?|ALL_PRIOR_YEARS_ACTUALS|BUSINESS_ALLOCATION|CURRENT_EAC|QE_FORECAST_VS_QE_PLAN|FORECAST_VS_BA|YE_RUN|RATE|QE_RUN|RATE_SUPPLEMENTARY)$'
    financial_cols_to_convert = [col for col in df.columns if pd.Series([col]).str.contains(financial_pattern, regex=True).any()]

    for col in financial_cols_to_convert:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '').str.strip().replace('', '0')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Refined identification of monthly columns
    monthly_col_pattern = re.compile(rf'^{current_year}_\d{{2}}_([AF]|CP)$')
    monthly_actuals_cols = []
    monthly_forecasts_cols = []
    monthly_plan_cols = []

    for col in df.columns:
        match = monthly_col_pattern.match(col)
        if match:
            col_type = match.group(1)
            if col_type == 'A':
                monthly_actuals_cols.append(col)
            elif col_type == 'F':
                monthly_forecasts_cols.append(col)
            elif col_type == 'CP':
                monthly_plan_cols.append(col)

    for col_list in [monthly_actuals_cols, monthly_forecasts_cols, monthly_plan_cols]:
        for col in col_list:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Calculate total Actuals, Forecasts, and Plans for the current year
    df[f'TOTAL_{current_year}_ACTUALS'] = df[monthly_actuals_cols].sum(axis=1) if monthly_actuals_cols else 0
    df[f'TOTAL_{current_year}_FORECASTS'] = df[monthly_forecasts_cols].sum(axis=1) if monthly_forecasts_cols else 0
    df[f'TOTAL_{current_year}_CAPITAL_PLAN'] = df[monthly_plan_cols].sum(axis=1) if monthly_plan_cols else 0

    if 'ALL_PRIOR_YEARS_ACTUALS' in df.columns:
        df['TOTAL_ACTUALS_TO_DATE'] = df['ALL_PRIOR_YEARS_ACTUALS'] + df[f'TOTAL_{current_year}_ACTUALS']
    else:
        df['TOTAL_ACTUALS_TO_DATE'] = df[f'TOTAL_{current_year}_ACTUALS']
        st.warning("Column 'ALL_PRIOR_YEARS_ACTUALS' not found. 'TOTAL_ACTUALS_TO_DATE' only includes current year actuals.")

    # --- Metrics Calculations ---
    ytd_actual_cols = [col for col in monthly_actuals_cols if int(col.split('_')[1]) <= current_month]
    df['SUM_ACTUAL_SPEND_YTD'] = df[ytd_actual_cols].sum(axis=1) if ytd_actual_cols else 0
    df['SUM_OF_FORECASTED_NUMBERS'] = df[f'TOTAL_{current_year}_FORECASTS']
    df['RUN_RATE_PER_MONTH'] = (df[f'TOTAL_{current_year}_ACTUALS'] + df[f'TOTAL_{current_year}_FORECASTS']) / 12

    if 'BUSINESS_ALLOCATION' in df.columns:
        df['CAPITAL_VARIANCE'] = df['BUSINESS_ALLOCATION'] - df[f'TOTAL_{current_year}_FORECASTS']
        df['CAPITAL_UNDERSPEND'] = df['CAPITAL_VARIANCE'].apply(lambda x: x if x > 0 else 0)
        df['CAPITAL_OVERSPEND'] = df['CAPITAL_VARIANCE'].apply(lambda x: abs(x) if x < 0 else 0)
    else:
        df['CAPITAL_VARIANCE'] = 0
        df['CAPITAL_UNDERSPEND'] = 0
        df['CAPITAL_OVERSPEND'] = 0
        st.warning("Column 'BUSINESS_ALLOCATION' not found for calculating under/over spend.")

    df['NET_REALLOCATION_AMOUNT'] = df['CAPITAL_UNDERSPEND'] - df['CAPITAL_OVERSPEND']

    # --- NEW: Average Spend Calculations ---
    num_actual_months = len(ytd_actual_cols) if ytd_actual_cols else 1
    num_forecast_months = len(monthly_forecasts_cols) if monthly_forecasts_cols else 1
    df['AVG_ACTUAL_SPEND'] = df['SUM_ACTUAL_SPEND_YTD'] / num_actual_months
    df['AVG_FORECAST_SPEND'] = df[f'TOTAL_{current_year}_FORECASTS'] / num_forecast_months
    
    # --- NEW: Total Spend Variance Calculation ---
    df['TOTAL_SPEND_VARIANCE'] = df[f'TOTAL_{current_year}_ACTUALS'] - df[f'TOTAL_{current_year}_FORECASTS']


    # --- Average Monthly Spread Performance Methodology ---
    monthly_af_variance_cols = []
    for i in range(1, 13):
        actual_col = f'{current_year}_{i:02d}_A'
        forecast_col = f'{current_year}_{i:02d}_F'
        variance_col_name = f'{current_year}_{i:02d}_AF_VARIANCE'
        if actual_col in df.columns and forecast_col in df.columns:
            df[variance_col_name] = df[actual_col] - df[forecast_col]
            monthly_af_variance_cols.append(variance_col_name)

    if monthly_af_variance_cols:
        df['AVERAGE_MONTHLY_SPREAD_SCORE'] = df[monthly_af_variance_cols].abs().mean(axis=1)
    else:
        df['AVERAGE_MONTHLY_SPREAD_SCORE'] = 0

    return df

# --- Streamlit App Layout ---
st.title("💰 Capital Project Portfolio Dashboard")
st.markdown("""
    This dashboard provides an interactive overview of your capital projects, allowing you to track financials,
    monitor trends, and identify variances.
""")

uploaded_file = st.file_uploader("Upload your Capital Project CSV file", type=["csv"])

if uploaded_file is not None:
    df = load_data(uploaded_file)

    if not df.empty:
        # --- Sidebar Filters ---
        st.sidebar.header("Filter Projects")

        filter_columns = {
            "PORTFOLIO_OBS_LEVEL1": "Select Portfolio Level",
            "SUB_PORTFOLIO_OBS_LEVEL2": "Select Sub-Portfolio Level",
            "PROJECT_MANAGER": "Select Project Manager",
            "BRS_CLASSIFICATION": "Select BRS Classification",
            "FUND_DECISION": "Select Fund Decision"
        }

        selected_filters = {}
        for col_name, display_name in filter_columns.items():
            if col_name in df.columns:
                options = ['All'] + df[col_name].dropna().unique().tolist()
                selected_filters[col_name] = st.sidebar.selectbox(display_name, options)
            else:
                if col_name == "FUND_DECISION":
                    st.sidebar.info(f"Column '{col_name}' not found for filtering.")
                selected_filters[col_name] = 'All'

        filtered_df = df.copy()
        for col_name, selected_value in selected_filters.items():
            if selected_value != 'All' and col_name in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[col_name] == selected_value]

        if filtered_df.empty:
            st.warning("No projects match the selected filters. Please adjust your selections.")
            st.stop()

        # --- Key Metrics Overview ---
        st.subheader("Key Metrics Overview")
        col1, col2, col3 = st.columns(3)

        with col1:
            total_projects = len(filtered_df)
            st.metric(label="Number of Projects", value=total_projects)
        with col2:
            sum_actual_spend_ytd = filtered_df['SUM_ACTUAL_SPEND_YTD'].sum()
            st.metric(label="Sum Actual Spend (YTD)", value=f"${sum_actual_spend_ytd:,.2f}")
        with col3:
            sum_of_forecasted_numbers_sum = filtered_df['SUM_OF_FORECASTED_NUMBERS'].sum()
            st.metric(label="Sum Of Forecasted Numbers", value=f"${sum_of_forecasted_numbers_sum:,.2f}")

        col_new_metrics1, col_new_metrics2, col_new_metrics3, col_new_metrics4 = st.columns(4)
        with col_new_metrics1:
            run_rate_per_month = filtered_df['RUN_RATE_PER_MONTH'].mean()
            st.metric(label="Average Run Rate / Month", value=f"${run_rate_per_month:,.2f}")
        with col_new_metrics2:
            capital_underspend = filtered_df['CAPITAL_UNDERSPEND'].sum()
            st.metric(label="Total Potential Underspend", value=f"${capital_underspend:,.2f}")
        with col_new_metrics3:
            capital_overspend = filtered_df['CAPITAL_OVERSPEND'].sum()
            st.metric(label="Total Potential Overspend", value=f"${capital_overspend:,.2f}")
        with col_new_metrics4:
            net_reallocation_amount = filtered_df['NET_REALLOCATION_AMOUNT'].sum()
            st.metric(label="Net Reallocation Amount", value=f"${net_reallocation_amount:,.2f}")

        st.markdown("---")
        
        # --- Project Table ---
        st.subheader("Project Details")
        project_table_cols = [
            'PORTFOLIO_OBS_LEVEL1', 'SUB_PORTFOLIO_OBS_LEVEL2', 'MASTER_PROJECT_ID',
            'PROJECT_NAME', 'PROJECT_MANAGER', 'BRS_CLASSIFICATION', 'FUND_DECISION',
            'BUSINESS_ALLOCATION', 'CURRENT_EAC', 'ALL_PRIOR_YEARS_ACTUALS',
            f'TOTAL_{current_year}_ACTUALS', f'TOTAL_{current_year}_FORECASTS', f'TOTAL_{current_year}_CAPITAL_PLAN',
            'QE_FORECAST_VS_QE_PLAN', 'FORECAST_VS_BA',
            'CAPITAL_UNDERSPEND', 'CAPITAL_OVERSPEND', 'NET_REALLOCATION_AMOUNT',
            'AVERAGE_MONTHLY_SPREAD_SCORE'
        ]
        project_table_cols_present = [col for col in project_table_cols if col in filtered_df.columns]
        
        financial_format_map = {
            col: "${:,.2f}" for col in project_table_cols_present if col in [
                'BUSINESS_ALLOCATION', 'CURRENT_EAC', 'ALL_PRIOR_YEARS_ACTUALS',
                f'TOTAL_{current_year}_ACTUALS', f'TOTAL_{current_year}_FORECASTS', f'TOTAL_{current_year}_CAPITAL_PLAN',
                'CAPITAL_UNDERSPEND', 'CAPITAL_OVERSPEND', 'NET_REALLOCATION_AMOUNT',
                'AVERAGE_MONTHLY_SPREAD_SCORE'
            ]
        }
        if 'QE_FORECAST_VS_QE_PLAN' in project_table_cols_present:
            financial_format_map['QE_FORECAST_VS_QE_PLAN'] = "{:,.2f}"
        if 'FORECAST_VS_BA' in project_table_cols_present:
            financial_format_map['FORECAST_VS_BA'] = "{:,.2f}"

        project_details_table = filtered_df[project_table_cols_present].style.format(financial_format_map)
        st.dataframe(project_details_table, use_container_width=True, hide_index=True)

        st.markdown("---")
        
        # --- Monthly Spend Trends ---
        # ... (This section remains unchanged)
        
        st.markdown("---")
        
        # --- Variance Analysis ---
        # ... (This section remains unchanged)

        st.markdown("---")
        
        # --- Capital Allocation Breakdown ---
        # ... (This section remains unchanged)

        st.markdown("---")

        # --- NEW FEATURE: SPEND VARIANCE ANALYSIS ---
        st.subheader("🔎 Project Spend Variance Analysis")
        st.markdown("""
        These charts compare the total and average spend (Actuals vs. Forecasts) for each project. 
        They are sorted to show the projects with the greatest difference between what was spent and what was forecasted.
        """)

        # Determine the number of projects to show in the charts
        num_projects_to_show = st.slider(
            "Select number of projects to display in variance charts:",
            min_value=5,
            max_value=min(50, total_projects),
            value=min(15, total_projects),
            step=5
        )

        # Chart 1: Total Actual vs. Forecast Spend
        st.write(f"#### Total Spend: Actuals vs. Forecast ({current_year})")
        
        # Sort by the absolute variance to find projects with the largest differences
        variance_df = filtered_df.reindex(filtered_df['TOTAL_SPEND_VARIANCE'].abs().sort_values(ascending=False).index)
        variance_df = variance_df.head(num_projects_to_show)

        total_spend_chart_df = variance_df[['PROJECT_NAME', f'TOTAL_{current_year}_ACTUALS', f'TOTAL_{current_year}_FORECASTS']].melt(
            id_vars='PROJECT_NAME',
            var_name='Spend Type',
            value_name='Amount'
        )
        total_spend_chart_df['Spend Type'] = total_spend_chart_df['Spend Type'].replace({
            f'TOTAL_{current_year}_ACTUALS': 'Total Actuals',
            f'TOTAL_{current_year}_FORECASTS': 'Total Forecasts'
        })
        
        fig_total_spend_variance = px.bar(
            total_spend_chart_df,
            y='PROJECT_NAME',
            x='Amount',
            color='Spend Type',
            barmode='group',
            orientation='h',
            title='Total Spend Variance by Project',
            labels={'Amount': 'Amount ($)', 'PROJECT_NAME': 'Project'},
            height=max(400, num_projects_to_show * 35) # Dynamic height
        )
        fig_total_spend_variance.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_total_spend_variance, use_container_width=True)

        # Chart 2: Average Monthly Spend
        st.write(f"#### Average Monthly Spend: Actuals vs. Forecast ({current_year})")

        avg_spend_chart_df = variance_df[['PROJECT_NAME', 'AVG_ACTUAL_SPEND', 'AVG_FORECAST_SPEND']].melt(
            id_vars='PROJECT_NAME',
            var_name='Spend Type',
            value_name='Amount'
        )
        avg_spend_chart_df['Spend Type'] = avg_spend_chart_df['Spend Type'].replace({
            'AVG_ACTUAL_SPEND': 'Average Actuals (YTD)',
            'AVG_FORECAST_SPEND': 'Average Forecasts (Annual)'
        })

        fig_avg_spend_variance = px.bar(
            avg_spend_chart_df,
            y='PROJECT_NAME',
            x='Amount',
            color='Spend Type',
            barmode='group',
            orientation='h',
            title='Average Monthly Spend Variance by Project',
            labels={'Amount': 'Amount ($)', 'PROJECT_NAME': 'Project'},
            height=max(400, num_projects_to_show * 35) # Dynamic height
        )
        fig_avg_spend_variance.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_avg_spend_variance, use_container_width=True)
        
        st.markdown("---")

        # --- NEW FEATURE: BUDGET IMPACT & REALLOCATION ---
        st.subheader("🎯 Budget Impact and Reallocation Insights")

        col_impact1, col_impact2 = st.columns(2)

        with col_impact1:
            st.write("#### Projects with Largest Forecasted Overspend")
            st.markdown("These projects are forecasted to exceed their `BUSINESS_ALLOCATION`. A review of their forecasts, scope, or budget may be required.")
            overspend_projects = filtered_df[filtered_df['CAPITAL_OVERSPEND'] > 0].sort_values('CAPITAL_OVERSPEND', ascending=False)
            
            if not overspend_projects.empty:
                st.dataframe(overspend_projects[[
                    'PROJECT_NAME', 'BUSINESS_ALLOCATION', f'TOTAL_{current_year}_FORECASTS', 'CAPITAL_OVERSPEND'
                ]].head().style.format({
                    'BUSINESS_ALLOCATION': "${:,.2f}", f'TOTAL_{current_year}_FORECASTS': "${:,.2f}", 'CAPITAL_OVERSPEND': "${:,.2f}"
                }), use_container_width=True, hide_index=True)
            else:
                st.info("No projects are currently forecasting an overspend.")

        with col_impact2:
            st.write("#### Projects with Largest Potential Underspend")
            st.markdown("These projects have the largest forecasted underspend, representing potential capital that could be reallocated to other strategic priorities.")
            underspend_projects = filtered_df[filtered_df['CAPITAL_UNDERSPEND'] > 0].sort_values('CAPITAL_UNDERSPEND', ascending=False)

            if not underspend_projects.empty:
                st.dataframe(underspend_projects[[
                    'PROJECT_NAME', 'BUSINESS_ALLOCATION', f'TOTAL_{current_year}_FORECASTS', 'CAPITAL_UNDERSPEND'
                ]].head().style.format({
                    'BUSINESS_ALLOCATION': "${:,.2f}", f'TOTAL_{current_year}_FORECASTS': "${:,.2f}", 'CAPITAL_UNDERSPEND': "${:,.2f}"
                }), use_container_width=True, hide_index=True)
            else:
                st.info("No projects are currently forecasting an underspend.")
        
        if not overspend_projects.empty and not underspend_projects.empty:
             st.success(f"""
            **Reallocation Suggestion:** There is a total potential underspend of **${capital_underspend:,.2f}** which could be used to cover the total potential overspend of **${capital_overspend:,.2f}**. 
            Consider reviewing the projects listed above for potential capital reallocation.
            """)
        
        st.markdown("---")

        # --- Detailed Project Financials (on selection) ---
        # ... (This section remains unchanged)

        st.markdown("---")
        
        # --- Project Performance ---
        st.subheader("🏆 Project Performance")

        # UPDATED: Add explanation for the performance score
        if 'AVERAGE_MONTHLY_SPREAD_SCORE' in filtered_df.columns:
            st.info("""
            **How is project performance ranked?**

            Project performance is determined by the **'Average Monthly Spread Score'**. Here’s how it works:
            1.  For each month, we calculate the **variance** (the absolute difference) between the project's actual spend and its forecasted spend.
            2.  The final score is the **average of these monthly variances** across the year for each project.
            
            A **lower score is better**, indicating that a project's actual costs are closely tracking its forecast, making it more predictable. A **higher score** suggests volatility and highlights projects that may need closer monitoring.
            """)

            project_performance_ranked = filtered_df.sort_values('AVERAGE_MONTHLY_SPREAD_SCORE')

            st.write("#### Top 5 Best Behaving Projects (Lowest Avg. Monthly Spread)")
            st.dataframe(project_performance_ranked.head(5)[[
                'PROJECT_NAME', 'AVERAGE_MONTHLY_SPREAD_SCORE'
            ]].style.format({
                'AVERAGE_MONTHLY_SPREAD_SCORE': "${:,.2f}"
            }), use_container_width=True, hide_index=True)

            st.write("#### Bottom 5 Worst Behaving Projects (Highest Avg. Monthly Spread)")
            st.dataframe(project_performance_ranked.tail(5).sort_values('AVERAGE_MONTHLY_SPREAD_SCORE', ascending=False)[[
                'PROJECT_NAME', 'AVERAGE_MONTHLY_SPREAD_SCORE'
            ]].style.format({
                'AVERAGE_MONTHLY_SPREAD_SCORE': "${:,.2f}"
            }), use_container_width=True, hide_index=True)
        else:
            st.info("Column 'AVERAGE_MONTHLY_SPREAD_SCORE' not found for Project Performance analysis.")

        st.markdown("---")

        # --- Report Generation Feature ---
        # ... (This section remains unchanged, but you might want to add the new charts to the report later)
        st.subheader("Generate Professional Report")
        st.markdown("Click the button below to generate a comprehensive HTML report of the current dashboard view (Note: New charts are not yet included in the report).")
        if st.button("Generate Report (HTML)"):
            st.warning("Report generation function needs to be updated to include the new charts. This feature is currently disabled.", icon="⚠️")


    else:
        st.warning("Please upload a CSV file with valid data to proceed.")

else:
    st.info("Upload your Capital Project CSV file to get started!")

st.markdown("---")

with st.expander("View Application Source Code"):
    # Exclude the report generation function from the displayed source code for brevity
    # as it's long and not part of the core logic being updated right now.
    st.code(inspect.getsource(load_data))
    st.code("# --- Main App Layout ---\n# ... (Full app layout code runs here)")
