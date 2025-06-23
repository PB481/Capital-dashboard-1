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
        # Replace problematic characters, but ensure '.' is handled for numerical parts if it appears.
        # Keeping '-' as '_' is also fine here.
        col_name = str(col_name).strip().replace(' ', '_').replace('+', '_').replace('.', '_').replace('-', '_')
        # Replace multiple underscores with a single underscore
        col_name = '_'.join(filter(None, col_name.split('_')))
        col_name = col_name.upper()

        # Specific corrections for common typos/inconsistencies
        corrections = {
            'PROJEC_TID': 'PROJECT_ID',
            'INI_MATIVE_PROGRAM': 'INITIATIVE_PROGRAM',
            'ALL_PRIOR_YEARS_A': 'ALL_PRIOR_YEARS_ACTUALS',
            'C_URRENT_EAC': 'CURRENT_EAC',
            'QE_RUN_RATE': 'QE_RUN_RATE',
            'RATE_1': 'RATE_SUPPLEMENTARY' # Example of better naming for duplicate 'RATE'
        }
        return corrections.get(col_name, col_name)

    # Apply column name cleaning
    df.columns = [clean_col_name(col) for col in df.columns]

    # Handle duplicate column names by making them unique (e.g., Rate, Rate_1)
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

    # Identify financial columns that need numeric conversion
    # Dynamically find columns that look like financial data (e.g., end with _A, _F, _CP or are specific financial metrics)
    # Adjusted regex to handle potential double underscore after year/month if clean_col_name accidentally creates it.
    financial_pattern = r'^(20\d{2}_\d{2}_(A|F|CP)(_\d+)?|ALL_PRIOR_YEARS_ACTUALS|BUSINESS_ALLOCATION|CURRENT_EAC|QE_FORECAST_VS_QE_PLAN|FORECAST_VS_BA|YE_RUN|RATE|QE_RUN|RATE_SUPPLEMENTARY)$'
    financial_cols_to_convert = [col for col in df.columns if pd.Series([col]).str.contains(financial_pattern, regex=True).any()]

    # Convert identified financial columns to numeric, handling commas, spaces, and errors
    for col in financial_cols_to_convert:
        if col in df.columns: # Ensure column exists after cleaning
            df[col] = df[col].astype(str).str.replace(',', '').str.strip().replace('', '0')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- Refined identification of monthly columns using a strict regex pattern ---
    # This pattern ensures the format is YEAR_MM_TYPE (e.g., 2025_01_A, 2025_12_CP)
    # \d{{2}} ensures the month part is exactly two digits.
    # We use current_year from the global scope.
    monthly_col_pattern = re.compile(rf'^{current_year}_\d{{2}}_([AF]|CP)$')

    monthly_actuals_cols = []
    monthly_forecasts_cols = []
    monthly_plan_cols = []

    for col in df.columns:
        match = monthly_col_pattern.match(col)
        if match:
            # match.group(1) will capture the type suffix: 'A', 'F', or 'CP'
            col_type = match.group(1)
            if col_type == 'A':
                monthly_actuals_cols.append(col)
            elif col_type == 'F':
                monthly_forecasts_cols.append(col)
            elif col_type == 'CP':
                monthly_plan_cols.append(col)
    # --- END Refined monthly column identification ---

    # Ensure all identified monthly columns are numeric (redundant with previous step but good for safety)
    # This loop is still useful as a fallback check, but the list itself is now accurate
    for col_list in [monthly_actuals_cols, monthly_forecasts_cols, monthly_plan_cols]:
        for col in col_list:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Calculate total Actuals, Forecasts, and Plans for the current year
    df[f'TOTAL_{current_year}_ACTUALS'] = df[monthly_actuals_cols].sum(axis=1) if monthly_actuals_cols else 0
    # TOTAL_FORECASTS for the year (sum of all _F columns)
    df[f'TOTAL_{current_year}_FORECASTS'] = df[monthly_forecasts_cols].sum(axis=1) if monthly_forecasts_cols else 0
    df[f'TOTAL_{current_year}_CAPITAL_PLAN'] = df[monthly_plan_cols].sum(axis=1) if monthly_plan_cols else 0

    # Calculate Total Actuals to Date (Prior Years + Current Year Actuals)
    # This column is still calculated but won't be displayed in Key Metrics Overview
    if 'ALL_PRIOR_YEARS_ACTUALS' in df.columns:
        df['TOTAL_ACTUALS_TO_DATE'] = df['ALL_PRIOR_YEARS_ACTUALS'] + df[f'TOTAL_{current_year}_ACTUALS']
    else:
        df['TOTAL_ACTUALS_TO_DATE'] = df[f'TOTAL_{current_year}_ACTUALS']
        st.warning("Column 'ALL_PRIOR_YEARS_ACTUALS' not found. 'TOTAL_ACTUALS_TO_DATE' only includes current year actuals.")

    # --- New Metrics Calculations ---

    # Sum of Actual Spend over the months (YTD) for the current year
    # Only sum actuals up to the current month (using global current_month)
    ytd_actual_cols = [col for col in monthly_actuals_cols if int(col.split('_')[1]) <= current_month]
    df['SUM_ACTUAL_SPEND_YTD'] = df[ytd_actual_cols].sum(axis=1) if ytd_actual_cols else 0

    # 'Sum Of Forecasted Numbers' (Total Annual Forecast)
    # This now sums ALL _F columns for the current year
    df['SUM_OF_FORECASTED_NUMBERS'] = df[f'TOTAL_{current_year}_FORECASTS']

    # Run rate per month based on actuals, forecast, and capital plans
    # Simplistic run rate: Total (Actuals + Forecasts) for the year divided by 12 months
    df['RUN_RATE_PER_MONTH'] = (df[f'TOTAL_{current_year}_ACTUALS'] + df[f'TOTAL_{current_year}_FORECASTS']) / 12

    # Capital Total Under Spend and Overspend
    # Assuming 'BUSINESS_ALLOCATION' is the target for comparison
    if 'BUSINESS_ALLOCATION' in df.columns:
        df['CAPITAL_VARIANCE'] = df['BUSINESS_ALLOCATION'] - df[f'TOTAL_{current_year}_FORECASTS']
        df['CAPITAL_UNDERSPEND'] = df['CAPITAL_VARIANCE'].apply(lambda x: x if x > 0 else 0)
        df['CAPITAL_OVERSPEND'] = df['CAPITAL_VARIANCE'].apply(lambda x: abs(x) if x < 0 else 0)
    else:
        df['CAPITAL_VARIANCE'] = 0
        df['CAPITAL_UNDERSPEND'] = 0
        df['CAPITAL_OVERSPEND'] = 0
        st.warning("Column 'BUSINESS_ALLOCATION' not found for calculating under/over spend.")

    # Net amount to confirm if we need to reallocate capital
    df['NET_REALLOCATION_AMOUNT'] = df['CAPITAL_UNDERSPEND'] - df['CAPITAL_OVERSPEND']

    # --- NEW METHODOLOGY FOR PERFORMANCE ---
    # Calculate month-to-month Actuals vs Forecasts variances
    monthly_af_variance_cols = []
    for i in range(1, 13): # For all 12 months
        actual_col = f'{current_year}_{i:02d}_A'
        forecast_col = f'{current_year}_{i:02d}_F'
        variance_col_name = f'{current_year}_{i:02d}_AF_VARIANCE'

        if actual_col in df.columns and forecast_col in df.columns:
            df[variance_col_name] = df[actual_col] - df[forecast_col]
            monthly_af_variance_cols.append(variance_col_name)
        else:
            # If a month's A or F column is missing, the variance for that month will be considered 0.
            # This avoids errors but might mask missing data.
            df[variance_col_name] = 0
            monthly_af_variance_cols.append(variance_col_name)


    # Calculate the total monthly spread score (sum of absolute variances) for each project
    if monthly_af_variance_cols:
        df['TOTAL_MONTHLY_SPREAD_SCORE'] = df[monthly_af_variance_cols].abs().sum(axis=1)
    else:
        df['TOTAL_MONTHLY_SPREAD_SCORE'] = 0
    # --- END NEW METHODOLOGY ---

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

        # Define filter columns and their display names
        filter_columns = {
            "PORTFOLIO_OBS_LEVEL1": "Select Portfolio Level",
            "SUB_PORTFOLIO_OBS_LEVEL2": "Select Sub-Portfolio Level",
            "PROJECT_MANAGER": "Select Project Manager",
            "BRS_CLASSIFICATION": "Select BRS Classification",
            "FUND_DECISION": "Select Fund Decision" # New Filter
        }

        selected_filters = {}
        for col_name, display_name in filter_columns.items():
            if col_name in df.columns:
                options = ['All'] + df[col_name].dropna().unique().tolist()
                selected_filters[col_name] = st.sidebar.selectbox(display_name, options)
            else:
                # Only show info if the column is explicitly expected by the user (like new FUND_DECISION)
                # For existing ones, load_data handles warnings.
                if col_name == "FUND_DECISION":
                    st.sidebar.info(f"Column '{col_name}' not found for filtering.")
                selected_filters[col_name] = 'All' # Set to 'All' if column is missing

        # Apply filters
        filtered_df = df.copy()
        for col_name, selected_value in selected_filters.items():
            if selected_value != 'All' and col_name in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[col_name] == selected_value]

        # Handle case where filtering results in an empty DataFrame
        if filtered_df.empty:
            st.warning("No projects match the selected filters. Please adjust your selections.")
            st.stop() # Stop execution if no data is left after filtering

        # --- Key Metrics Overview ---
        st.subheader("Key Metrics Overview")
        # UPDATED: Adjusted columns for the first row after metric removals
        col1, col2, col3 = st.columns(3) # Projects, YTD Actuals, Sum of Forecasted Numbers

        # Removed: Total Business Allocation, Total Current EAC, Total Capital Plan, Total Actuals To Date
        # Remaining and reordered metrics for first row
        with col1: # Reordered
            total_projects = len(filtered_df)
            st.metric(label="Number of Projects", value=total_projects)
        with col2: # Reordered
            sum_actual_spend_ytd = filtered_df['SUM_ACTUAL_SPEND_YTD'].sum() if 'SUM_ACTUAL_SPEND_YTD' in filtered_df.columns else 0
            st.metric(label="Sum Actual Spend (YTD)", value=f"${sum_actual_spend_ytd:,.2f}")
        with col3: # UPDATED: Changed label and source column
            sum_of_forecasted_numbers_sum = filtered_df['SUM_OF_FORECASTED_NUMBERS'].sum() if 'SUM_OF_FORECASTED_NUMBERS' in filtered_df.columns else 0
            st.metric(label="Sum Of Forecasted Numbers", value=f"${sum_of_forecasted_numbers_sum:,.2f}")

        # Metrics for the second row remain the same (Run Rate, Under/Over Spend, Net Reallocation)
        col_new_metrics1, col_new_metrics2, col_new_metrics3, col_new_metrics4 = st.columns(4)
        with col_new_metrics1:
            run_rate_per_month = filtered_df['RUN_RATE_PER_MONTH'].mean() if 'RUN_RATE_PER_MONTH' in filtered_df.columns else 0
            st.metric(label="Average Run Rate / Month", value=f"${run_rate_per_month:,.2f}")
        with col_new_metrics2:
            capital_underspend = filtered_df['CAPITAL_UNDERSPEND'].sum() if 'CAPITAL_UNDERSPEND' in filtered_df.columns else 0
            st.metric(label="Total Potential Underspend", value=f"${capital_underspend:,.2f}")
        with col_new_metrics3:
            capital_overspend = filtered_df['CAPITAL_OVERSPEND'].sum() if 'CAPITAL_OVERSPEND' in filtered_df.columns else 0
            st.metric(label="Total Potential Overspend", value=f"${capital_overspend:,.2f}")
        with col_new_metrics4:
            net_reallocation_amount = filtered_df['NET_REALLOCATION_AMOUNT'].sum() if 'NET_REALLOCATION_AMOUNT' in filtered_df.columns else 0
            st.metric(label="Net Reallocation Amount", value=f"${net_reallocation_amount:,.2f}")


        st.markdown("---")

        # --- Project Table ---
        st.subheader("Project Details")
        # Define columns to display in the project details table
        project_table_cols = [
            'PORTFOLIO_OBS_LEVEL1', 'SUB_PORTFOLIO_OBS_LEVEL2', 'MASTER_PROJECT_ID',
            'PROJECT_NAME', 'PROJECT_MANAGER', 'BRS_CLASSIFICATION', 'FUND_DECISION',
            'BUSINESS_ALLOCATION', 'CURRENT_EAC', 'ALL_PRIOR_YEARS_ACTUALS',
            f'TOTAL_{current_year}_ACTUALS', f'TOTAL_{current_year}_FORECASTS', f'TOTAL_{current_year}_CAPITAL_PLAN',
            'QE_FORECAST_VS_QE_PLAN', 'FORECAST_VS_BA',
            'CAPITAL_UNDERSPEND', 'CAPITAL_OVERSPEND', 'NET_REALLOCATION_AMOUNT',
            'TOTAL_MONTHLY_SPREAD_SCORE' # Added new metric for project-level tracking
        ]
        # Filter to only include columns that actually exist in the filtered_df
        project_table_cols_present = [col for col in project_table_cols if col in filtered_df.columns]

        # Define formatting for financial columns in the table
        financial_format_map = {
            col: "${:,.2f}" for col in project_table_cols_present if col in [
                'BUSINESS_ALLOCATION', 'CURRENT_EAC', 'ALL_PRIOR_YEARS_ACTUALS',
                f'TOTAL_{current_year}_ACTUALS', f'TOTAL_{current_year}_FORECASTS', f'TOTAL_{current_year}_CAPITAL_PLAN',
                'CAPITAL_UNDERSPEND', 'CAPITAL_OVERSPEND', 'NET_REALLOCATION_AMOUNT',
                'TOTAL_MONTHLY_SPREAD_SCORE' # Format the new score as currency
            ]
        }
        # Add specific formats for variance columns if present
        if 'QE_FORECAST_VS_QE_PLAN' in project_table_cols_present:
            financial_format_map['QE_FORECAST_VS_QE_PLAN'] = "{:,.2f}"
        if 'FORECAST_VS_BA' in project_table_cols_present:
            financial_format_map['FORECAST_VS_BA'] = "{:,.2f}"

        project_details_table = filtered_df[project_table_cols_present].style.format(financial_format_map)
        st.dataframe(project_details_table, use_container_width=True, hide_index=True)

        st.markdown("---")

        # --- Monthly Spend Trends ---
        st.subheader(f"{current_year} Monthly Spend Trends")

        # --- Refined identification of monthly columns for filtering (same logic as load_data) ---
        # We use current_year_str from the global scope.
        monthly_col_pattern_filtered = re.compile(rf'^{current_year_str}_\d{{2}}_([AF]|CP)$')

        monthly_actuals_cols_filtered = []
        monthly_forecasts_cols_filtered = []
        monthly_plan_cols_filtered = []

        for col in filtered_df.columns:
            match = monthly_col_pattern_filtered.match(col)
            if match:
                col_type = match.group(1)
                if col_type == 'A':
                    monthly_actuals_cols_filtered.append(col)
                elif col_type == 'F':
                    monthly_forecasts_cols_filtered.append(col)
                elif col_type == 'CP':
                    monthly_plan_cols_filtered.append(col)
        # --- END Refined monthly column identification ---

        monthly_combined_df = pd.DataFrame()
        data_to_concat = []

        # Actuals (historic)
        actuals_data_points = []
        for col in monthly_actuals_cols_filtered:
            # The 'int(col.split('_')[1])' is now safe due to the regex filtering above
            month_num = int(col.split('_')[1])
            if month_num <= current_month: # Use global current_month
                actuals_data_points.append({'Month': f'{current_year_str}_{month_num:02d}', 'Amount': filtered_df[col].sum(), 'Type': 'Actuals'})
        if actuals_data_points and sum(d['Amount'] for d in actuals_data_points) != 0: # Only add if sum is not zero
            data_to_concat.append(pd.DataFrame(actuals_data_points))

        # Forecasts (future)
        forecasts_data_points = []
        for col in monthly_forecasts_cols_filtered:
            month_num = int(col.split('_')[1])
            if month_num > current_month: # Use global current_month
                forecasts_data_points.append({'Month': f'{current_year_str}_{month_num:02d}', 'Amount': filtered_df[col].sum(), 'Type': 'Forecasts'})
        if forecasts_data_points and sum(d['Amount'] for d in forecasts_data_points) != 0: # Only add if sum is not zero
            data_to_concat.append(pd.DataFrame(forecasts_data_points))

        # Capital Plan (all months)
        plan_data_points = []
        for col in monthly_plan_cols_filtered:
            month_num = int(col.split('_')[1])
            plan_data_points.append({'Month': f'{current_year_str}_{month_num:02d}', 'Amount': filtered_df[col].sum(), 'Type': 'Capital Plan'})
        if plan_data_points and sum(d['Amount'] for d in plan_data_points) != 0: # Only add if sum is not zero
            data_to_concat.append(pd.DataFrame(plan_data_points))


        if data_to_concat:
            monthly_combined_df = pd.concat(data_to_concat)

            # Ensure month order for plotting
            month_order = [f'{current_year_str}_{i:02d}' for i in range(1, 13)]
            monthly_combined_df['Month_Sort'] = pd.Categorical(monthly_combined_df['Month'], categories=month_order, ordered=True)
            monthly_combined_df = monthly_combined_df.sort_values('Month_Sort')

            fig_monthly_trends = px.line(
                monthly_combined_df,
                x='Month_Sort',
                y='Amount',
                color='Type',
                title=f'Monthly Capital Trends (Actuals, Forecasts, Plan) for {current_year_str}',
                labels={'Month_Sort': 'Month', 'Amount': 'Amount ($)'},
                line_shape='linear',
                markers=True
            )
            fig_monthly_trends.update_layout(hovermode="x unified", legend_title_text='Type')
            fig_monthly_trends.update_xaxes(title_text=f"Month ({current_year_str})")
            fig_monthly_trends.update_yaxes(title_text="Amount ($)")
            st.plotly_chart(fig_monthly_trends, use_container_width=True)
        else:
            st.warning(f"No {current_year_str} monthly actuals, forecasts, or plan data found for trend analysis after filtering.")
            fig_monthly_trends = None # Explicitly set to None if no data

        st.markdown("---")

        # --- Variance Analysis ---
        st.subheader("Variance Analysis")
        col_var1, col_var2 = st.columns(2)
        fig_qe_variance = None
        fig_ba_variance = None

        if 'QE_FORECAST_VS_QE_PLAN' in filtered_df.columns and not filtered_df['QE_FORECAST_VS_QE_PLAN'].isnull().all():
            with col_var1:
                fig_qe_variance = px.bar(
                    filtered_df.sort_values('QE_FORECAST_VS_QE_PLAN', ascending=False), # Sort for better visualization
                    x='PROJECT_NAME',
                    y='QE_FORECAST_VS_QE_PLAN',
                    title='QE Forecast vs QE Plan Variance',
                    labels={'QE_FORECAST_VS_QE_PLAN': 'Variance'},
                    height=400
                )
                fig_qe_variance.update_layout(xaxis_title="Project Name", yaxis_title="Variance")
                st.plotly_chart(fig_qe_variance, use_container_width=True)
        else:
            with col_var1:
                st.info("Column 'QE_FORECAST_VS_QE_PLAN' not found or contains no data for variance analysis.")

        if 'FORECAST_VS_BA' in filtered_df.columns and not filtered_df['FORECAST_VS_BA'].isnull().all():
            with col_var2:
                fig_ba_variance = px.bar(
                    filtered_df.sort_values('FORECAST_VS_BA', ascending=False), # Sort for better visualization
                    x='PROJECT_NAME',
                    y='FORECAST_VS_BA',
                    title='Forecast vs Business Allocation Variance',
                    labels={'FORECAST_VS_BA': 'Variance'},
                    height=400
                )
                fig_ba_variance.update_layout(xaxis_title="Project Name", yaxis_title="Variance")
                st.plotly_chart(fig_ba_variance, use_container_width=True)
        else:
            with col_var2:
                st.info("Column 'FORECAST_VS_BA' not found or contains no data for variance analysis.")

        st.markdown("---")

        # --- Capital Allocation Breakdown ---
        st.subheader("Capital Allocation Breakdown")
        col_alloc1, col_alloc2, col_alloc3 = st.columns(3)
        fig_portfolio_alloc = None
        fig_sub_portfolio_alloc = None
        fig_brs_alloc = None

        if 'BUSINESS_ALLOCATION' in filtered_df.columns:
            with col_alloc1:
                if 'PORTFOLIO_OBS_LEVEL1' in filtered_df.columns and not filtered_df['PORTFOLIO_OBS_LEVEL1'].isnull().all():
                    fig_portfolio_alloc = px.pie(
                        filtered_df,
                        names='PORTFOLIO_OBS_LEVEL1',
                        values='BUSINESS_ALLOCATION',
                        title='Allocation by Portfolio Level',
                        hole=0.3
                    )
                    st.plotly_chart(fig_portfolio_alloc, use_container_width=True)
                else:
                    st.info("No 'PORTFOLIO_OBS_LEVEL1' data available for allocation.")

            with col_alloc2:
                if 'SUB_PORTFOLIO_OBS_LEVEL2' in filtered_df.columns and not filtered_df['SUB_PORTFOLIO_OBS_LEVEL2'].isnull().all():
                    fig_sub_portfolio_alloc = px.pie(
                        filtered_df,
                        names='SUB_PORTFOLIO_OBS_LEVEL2',
                        values='BUSINESS_ALLOCATION',
                        title='Allocation by Sub-Portfolio Level',
                        hole=0.3
                    )
                    st.plotly_chart(fig_sub_portfolio_alloc, use_container_width=True)
                else:
                    st.info("No 'SUB_PORTFOLIO_OBS_LEVEL2' data available for allocation.")

            with col_alloc3:
                if 'BRS_CLASSIFICATION' in filtered_df.columns and not filtered_df['BRS_CLASSIFICATION'].isnull().all():
                    fig_brs_alloc = px.pie(
                        filtered_df,
                        names='BRS_CLASSIFICATION',
                        values='BUSINESS_ALLOCATION',
                        title='Allocation by BRS Classification',
                        hole=0.3
                    )
                    st.plotly_chart(fig_brs_alloc, use_container_width=True)
                else:
                    st.info("No 'BRS_CLASSIFICATION' data available for allocation.")
        else:
            st.info("Column 'BUSINESS_ALLOCATION' not found for allocation breakdown.")

        st.markdown("---")

        # --- Detailed Project Financials (on selection) ---
        st.subheader("Detailed Project Financials")
        project_names = ['Select a Project'] + filtered_df['PROJECT_NAME'].dropna().unique().tolist()
        selected_project_name = st.selectbox("Select a project for detailed view:", project_names)

        project_details = None
        fig_project_monthly = None

        if selected_project_name != 'Select a Project':
            project_details = filtered_df[filtered_df['PROJECT_NAME'] == selected_project_name].iloc[0]

            st.write(f"### Details for: {project_details['PROJECT_NAME']}")

            # Display key financial metrics for the selected project
            col_d1, col_d2, col_d3 = st.columns(3)
            with col_d1:
                st.metric(label="Business Allocation", value=f"${project_details.get('BUSINESS_ALLOCATION', 0):,.2f}")
            with col_d2:
                st.metric(label="Current EAC", value=f"${project_details.get('CURRENT_EAC', 0):,.2f}")
            with col_d3:
                st.metric(label="All Prior Years Actuals", value=f"${project_details.get('ALL_PRIOR_YEARS_ACTUALS', 0):,.2f}")

            st.write(f"#### {current_year_str} Monthly Breakdown:")
            # Generate monthly breakdown DataFrame dynamically based on available columns
            monthly_breakdown_data = {'Month': [f"{current_year_str}_{i:02d}" for i in range(1, 13)]}
            monthly_types = {'_A': 'Actuals', '_F': 'Forecasts', '_CP': 'Capital Plan'}

            for suffix, display_name in monthly_types.items():
                col_prefix = f'{current_year_str}_'
                monthly_values = []
                for i in range(1, 13):
                    col_name_full = f"{col_prefix}{i:02d}{suffix}"
                    monthly_values.append(project_details.get(col_name_full, 0))
                monthly_breakdown_data[display_name] = monthly_values

            monthly_breakdown_df = pd.DataFrame(monthly_breakdown_data)

            # Format the monthly breakdown table
            monthly_format_map_details = {
                'Actuals': "${:,.2f}",
                'Forecasts': "${:,.2f}",
                'Capital Plan': "${:,.2f}"
            }
            st.dataframe(monthly_breakdown_df.style.format(monthly_format_map_details), use_container_width=True, hide_index=True)

            # Bar chart for monthly breakdown for the selected project
            monthly_project_melted = monthly_breakdown_df.melt(id_vars=['Month'], var_name='Type', value_name='Amount')

            fig_project_monthly = px.bar(
                monthly_project_melted,
                x='Month',
                y='Amount',
                color='Type',
                barmode='group',
                title=f'Monthly Financials for {selected_project_name}',
                labels={'Amount': 'Amount ($)'}
            )
            st.plotly_chart(fig_project_monthly, use_container_width=True)

        else:
            st.info("Select a project from the dropdown to see its detailed monthly financials.")

        st.markdown("---")

        # --- Project Manager Performance ---
        st.subheader("Project Manager Performance")

        # UPDATED: Project Manager Performance based on TOTAL_MONTHLY_SPREAD_SCORE
        if 'PROJECT_MANAGER' in filtered_df.columns and 'TOTAL_MONTHLY_SPREAD_SCORE' in filtered_df.columns:
            pm_performance = filtered_df.groupby('PROJECT_MANAGER').agg(
                Total_Monthly_Spread=('TOTAL_MONTHLY_SPREAD_SCORE', 'sum'),
                Number_of_Projects=('PROJECT_NAME', 'count') # Added count of projects for context
            ).reset_index()

            # Rank by Total_Monthly_Spread (lower is better)
            pm_performance = pm_performance.sort_values('Total_Monthly_Spread')

            st.write("#### Top 5 Project Managers (Closest to Monthly Forecasts)")
            st.dataframe(pm_performance.head(5).style.format({
                'Total_Monthly_Spread': "${:,.2f}"
            }), use_container_width=True, hide_index=True)

            st.write("#### Bottom 5 Project Managers (Furthest from Monthly Forecasts)")
            st.dataframe(pm_performance.tail(5).sort_values('Total_Monthly_Spread', ascending=False).style.format({
                'Total_Monthly_Spread': "${:,.2f}"
            }), use_container_width=True, hide_index=True)
        else:
            st.info("Required columns for Project Manager Performance (PROJECT_MANAGER, TOTAL_MONTHLY_SPREAD_SCORE) not found.")

        st.markdown("---")

        # --- Project Performance ---
        st.subheader("Project Performance")

        # UPDATED: Project Performance based on TOTAL_MONTHLY_SPREAD_SCORE
        if 'TOTAL_MONTHLY_SPREAD_SCORE' in filtered_df.columns:
            project_performance_ranked = filtered_df.sort_values('TOTAL_MONTHLY_SPREAD_SCORE')

            st.write("#### Top 5 Best Behaving Projects (Closest to Monthly Forecasts)")
            st.dataframe(project_performance_ranked.head(5)[[
                'PROJECT_NAME', 'TOTAL_MONTHLY_SPREAD_SCORE' # Display only relevant columns
            ]].style.format({
                'TOTAL_MONTHLY_SPREAD_SCORE': "${:,.2f}"
            }), use_container_width=True, hide_index=True)

            st.write("#### Bottom 5 Worst Behaving Projects (Furthest from Monthly Forecasts)")
            st.dataframe(project_performance_ranked.tail(5).sort_values('TOTAL_MONTHLY_SPREAD_SCORE', ascending=False)[[
                'PROJECT_NAME', 'TOTAL_MONTHLY_SPREAD_SCORE' # Display only relevant columns
            ]].style.format({
                'TOTAL_MONTHLY_SPREAD_SCORE': "${:,.2f}"
            }), use_container_width=True, hide_index=True)
        else:
            st.info("Column 'TOTAL_MONTHLY_SPREAD_SCORE' not found for Project Performance analysis.")


        st.markdown("---")

        # --- Report Generation Feature ---
        st.subheader("Generate Professional Report")
        st.markdown("Click the button below to generate a comprehensive HTML report of the current dashboard view.")

        # Function to generate the HTML report content (updated to include new metrics and tables)
        def generate_html_report(
            filtered_df: pd.DataFrame,
            total_projects: int,
            sum_actual_spend_ytd: float,
            sum_of_forecasted_numbers_sum: float, # UPDATED: Parameter name
            run_rate_per_month: float,
            capital_underspend: float,
            capital_overspend: float,
            net_reallocation_amount: float,
            monthly_combined_df: pd.DataFrame | None,
            fig_monthly_trends: go.Figure | None,
            fig_qe_variance: go.Figure | None,
            fig_ba_variance: go.Figure | None,
            fig_portfolio_alloc: go.Figure | None,
            fig_sub_portfolio_alloc: go.Figure | None,
            fig_brs_alloc: go.Figure | None,
            selected_project_name: str,
            project_details: pd.Series | None,
            fig_project_monthly: go.Figure | None
        ) -> str:
            """Generates a comprehensive HTML report of the dashboard state."""

            # Base HTML structure and styling
            report_html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Capital Project Portfolio Report</title>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; margin: 20px; color: #333; }}
        h1, h2, h3 {{ color: #004d40; }}
        .metric-container {{ display: flex; justify-content: space-around; flex-wrap: wrap; margin-bottom: 20px; }}
        .metric-box {{ border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 10px; flex: 1; min-width: 200px; text-align: center; background-color: #f9f9f9; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric-label {{ font-size: 0.9em; color: #555; }}
        .metric-value {{ font-size: 1.5em; font-weight: bold; color: #222; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #e6f2f0; }}
        .chart-container {{ margin-top: 30px; border: 1px solid #eee; padding: 10px; border-radius: 8px; background-color: #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
        .section-title {{ margin-top: 40px; border-bottom: 2px solid #004d40; padding-bottom: 10px; }}
        footer {{ text-align: center; margin-top: 50px; padding-top: 20px; border-top: 1px solid #eee; font-size: 0.8em; color: #777; }}
    </style>
</head>
<body>
    <h1>Capital Project Portfolio Report</h1>
    <p>Generated on: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <h2 class="section-title">Key Metrics Overview</h2>
    <div class="metric-container">
        <div class="metric-box">
            <div class="metric-label">Number of Projects</div>
            <div class="metric-value">{total_projects}</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">Sum Actual Spend (YTD)</div>
            <div class="metric-value">${sum_actual_spend_ytd:,.2f}</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">Sum Of Forecasted Numbers</div>
            <div class="metric-value">${sum_of_forecasted_numbers_sum:,.2f}</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">Average Run Rate / Month</div>
            <div class="metric-value">${run_rate_per_month:,.2f}</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">Total Potential Underspend</div>
            <div class="metric-value">${capital_underspend:,.2f}</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">Total Potential Overspend</div>
            <div class="metric-value">${capital_overspend:,.2f}</div>
        </div>
         <div class="metric-box">
            <div class="metric-label">Net Reallocation Amount</div>
            <div class="metric-value">${net_reallocation_amount:,.2f}</div>
        </div>
    </div>

    <h2 class="section-title">Filtered Project Details</h2>
    {filtered_df[project_table_cols_present].style.format(financial_format_map).to_html(index=False)}

    <h2 class="section-title">{current_year} Monthly Spend Trends</h2>
    <div class="chart-container">
        {fig_monthly_trends.to_html(full_html=False, include_plotlyjs='cdn') if fig_monthly_trends else '<p>No monthly trend data available.</p>'}
    </div>

    <h2 class="section-title">Variance Analysis</h2>
    <div style="display: flex; justify-content: space-around; flex-wrap: wrap;">
        <div class="chart-container" style="flex: 1; min-width: 45%;">
            {fig_qe_variance.to_html(full_html=False, include_plotlyjs='cdn') if fig_qe_variance else '<p>No QE Forecast vs QE Plan Variance data available.</p>'}
        </div>
        <div class="chart-container" style="flex: 1; min-width: 45%;">
            {fig_ba_variance.to_html(full_html=False, include_plotlyjs='cdn') if fig_ba_variance else '<p>No Forecast vs Business Allocation Variance data available.</p>'}
        </div>
    </div>

    <h2 class="section-title">Capital Allocation Breakdown</h2>
    <div style="display: flex; justify-content: space-around; flex-wrap: wrap;">
        <div class="chart-container" style="flex: 1; min-width: 30%;">
            {fig_portfolio_alloc.to_html(full_html=False, include_plotlyjs='cdn') if fig_portfolio_alloc else '<p>No Portfolio Level allocation data available.</p>'}
        </div>
        <div class="chart-container" style="flex: 1; min-width: 30%;">
            {fig_sub_portfolio_alloc.to_html(full_html=False, include_plotlyjs='cdn') if fig_sub_portfolio_alloc else '<p>No Sub-Portfolio Level allocation data available.</p>'}
        </div>
        <div class="chart-container" style="flex: 1; min-width: 30%;">
            {fig_brs_alloc.to_html(full_html=False, include_plotlyjs='cdn') if fig_brs_alloc else '<p>No BRS Classification allocation data available.</p>'}
        </div>
    </div>
"""
            # Add detailed project financials if a project is selected
            if selected_project_name != 'Select a Project' and project_details is not None and fig_project_monthly is not None:
                # Re-create monthly breakdown DF for report to ensure it has correct formatting
                monthly_breakdown_data_html = {'Month': [f"{current_year_str}_{i:02d}" for i in range(1, 13)]}
                monthly_types = {'_A': 'Actuals', '_F': 'Forecasts', '_CP': 'Capital Plan'}

                for suffix, display_name in monthly_types.items():
                    col_prefix = f'{current_year_str}_'
                    monthly_values_html = []
                    for i in range(1, 13):
                        col_name_full_html = f"{col_prefix}{i:02d}{suffix}"
                        monthly_values_html.append(project_details.get(col_name_full_html, 0))
                    monthly_breakdown_data_html[display_name] = monthly_values_html

                monthly_breakdown_df_html = pd.DataFrame(monthly_breakdown_data_html).style.format(monthly_format_map_details).to_html(index=False)

                report_html_content += f"""
                <h2 class="section-title">Detailed Financials for {selected_project_name}</h2>
                <div class="metric-container">
                    <div class="metric-box">
                        <div class="metric-label">Business Allocation</div>
                        <div class="metric-value">${project_details.get('BUSINESS_ALLOCATION', 0):,.2f}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Current EAC</div>
                        <div class="metric-value">${project_details.get('CURRENT_EAC', 0):,.2f}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">All Prior Years Actuals</div>
                        <div class="metric-value">${project_details.get('ALL_PRIOR_YEARS_ACTUALS', 0):,.2f}</div>
                    </div>
                </div>
                <h3>{current_year_str} Monthly Breakdown:</h3>
                {monthly_breakdown_df_html}
                <div class="chart-container">
                    {fig_project_monthly.to_html(full_html=False, include_plotlyjs='cdn')}
                </div>
                """
            else:
                report_html_content += """
                <h2 class="section-title">Detailed Project Financials</h2>
                <p>No project selected for detailed view in the report.</p>
                """

            # Add Project Manager Performance to report
            pm_report_html = ""
            if 'PROJECT_MANAGER' in filtered_df.columns and 'TOTAL_MONTHLY_SPREAD_SCORE' in filtered_df.columns:
                pm_performance = filtered_df.groupby('PROJECT_MANAGER').agg(
                    Total_Monthly_Spread=('TOTAL_MONTHLY_SPREAD_SCORE', 'sum'),
                    Number_of_Projects=('PROJECT_NAME', 'count')
                ).reset_index()

                pm_performance_sorted = pm_performance.sort_values('Total_Monthly_Spread')

                pm_report_html += "<h3>Top 5 Project Managers (Closest to Monthly Forecasts)</h3>"
                pm_report_html += pm_performance_sorted.head(5).style.format({
                    'Total_Monthly_Spread': "${:,.2f}"
                }).to_html(index=False)

                pm_report_html += "<h3>Bottom 5 Project Managers (Furthest from Monthly Forecasts)</h3>"
                pm_report_html += pm_performance_sorted.tail(5).sort_values('Total_Monthly_Spread', ascending=False).style.format({
                    'Total_Monthly_Spread': "${:,.2f}"
                }).to_html(index=False)
            else:
                pm_report_html += "<p>Required columns for Project Manager Performance not found.</p>"

            report_html_content += f"""
            <h2 class="section-title">Project Manager Performance</h2>
            {pm_report_html}
            """

            # Add Project Performance to report
            project_perf_report_html = ""
            if 'TOTAL_MONTHLY_SPREAD_SCORE' in filtered_df.columns:
                project_performance_ranked = filtered_df.sort_values('TOTAL_MONTHLY_SPREAD_SCORE')

                project_perf_report_html += "<h3>Top 5 Best Behaving Projects (Closest to Monthly Forecasts)</h3>"
                project_perf_report_html += project_performance_ranked.head(5)[[
                    'PROJECT_NAME', 'TOTAL_MONTHLY_SPREAD_SCORE'
                ]].style.format({
                    'TOTAL_MONTHLY_SPREAD_SCORE': "${:,.2f}"
                }).to_html(index=False)

                project_perf_report_html += "<h3>Bottom 5 Worst Behaving Projects (Furthest from Monthly Forecasts)</h3>"
                project_perf_report_html += project_performance_ranked.tail(5).sort_values('TOTAL_MONTHLY_SPREAD_SCORE', ascending=False)[[
                    'PROJECT_NAME', 'TOTAL_MONTHLY_SPREAD_SCORE'
                ]].style.format({
                    'TOTAL_MONTHLY_SPREAD_SCORE': "${:,.2f}"
                }).to_html(index=False)
            else:
                project_perf_report_html += "<p>Column 'TOTAL_MONTHLY_SPREAD_SCORE' not found for Project Performance analysis.</p>"

            report_html_content += f"""
            <h2 class="section-title">Project Performance</h2>
            {project_perf_report_html}
            """


            report_html_content += """
                <footer>
                    <p>Generated by Capital Project Portfolio Dashboard Streamlit App.</p>
                </footer>
            </body>
            </html>
            """
            return report_html_content

        if st.button("Generate Report (HTML)"):
            report_monthly_combined_df = monthly_combined_df if 'monthly_combined_df' in locals() and not monthly_combined_df.empty else None
            report_project_details = project_details if selected_project_name != 'Select a Project' else None
            report_fig_project_monthly = fig_project_monthly if selected_project_name != 'Select a Project' else None

            report_content = generate_html_report(
                filtered_df,
                total_projects,
                sum_actual_spend_ytd, sum_of_forecasted_numbers_sum,
                run_rate_per_month, capital_underspend, capital_overspend, net_reallocation_amount,
                report_monthly_combined_df, fig_monthly_trends, fig_qe_variance, fig_ba_variance,
                fig_portfolio_alloc, fig_sub_portfolio_alloc, fig_brs_alloc,
                selected_project_name, report_project_details, report_fig_project_monthly
            )

            st.download_button(
                label="Download Report as HTML",
                data=report_content,
                file_name="capital_project_report.html",
                mime="text/html"
            )

    else:
        st.warning("Please upload a CSV file with valid data to proceed.")

else:
    st.info("Upload your Capital Project CSV file to get started!")

st.markdown("---")

with st.expander("View Application Source Code"):
    source_code = inspect.getsource(inspect.currentframe())
    st.code(source_code, language='python')
