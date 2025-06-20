import streamlit as st
import pandas as pd
import plotly.express as px
import io
import inspect

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
        col_name = str(col_name).strip().replace(' ', '_').replace('+', '_').replace('.', '').replace('-', '_')
        # Replace multiple underscores with a single underscore
        col_name = '_'.join(filter(None, col_name.split('_')))
        col_name = col_name.upper()

        # Specific corrections for common typos/inconsistencies
        corrections = {
            'PROJEC_TID': 'PROJECT_ID',
            'INI_MATIVE_PROGRAM': 'INITIATIVE_PROGRAM',
            'ALL_PRIOR_YEARS_A': 'ALL_PRIOR_YEARS_ACTUALS',
            'C_URRENT_EAC': 'CURRENT_EAC',
            'QE_RUN_RATE': 'QE_RUN_RATE', # Ensure consistency
            'RATE_1': 'RATE_SUPPLEMENTARY' # Example of better naming for duplicate 'RATE'
        }
        return corrections.get(col_name, col_name)

    # Apply column name cleaning
    df.columns = [clean_col_name(col) for col in df.columns]

    # Handle duplicate column names by making them unique (e.g., Rate, Rate_1)
    # This approach appends a number only if a duplicate truly exists
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
    financial_pattern = r'^(20\d{2}_\d{2}_[AFCPL]|ALL_PRIOR_YEARS_ACTUALS|BUSINESS_ALLOCATION|CURRENT_EAC|QE_FORECAST_VS_QE_PLAN|FORECAST_VS_BA|YE_RUN|RATE|QE_RUN|RATE_SUPPLEMENTARY)$'
    financial_cols_to_convert = [col for col in df.columns if pd.Series([col]).str.contains(financial_pattern, regex=True).any()]

    # Convert identified financial columns to numeric, handling commas, spaces, and errors
    for col in financial_cols_to_convert:
        if col in df.columns: # Ensure column exists after cleaning
            df[col] = df[col].astype(str).str.replace(',', '').str.strip().replace('', '0')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Identify monthly columns for 2025 (or any year starting with '20' followed by two digits)
    monthly_actuals_cols = [col for col in df.columns if col.startswith('20') and col.endswith('_A')]
    monthly_forecasts_cols = [col for col in df.columns if col.startswith('20') and col.endswith('_F')]
    monthly_plan_cols = [col for col in df.columns if col.startswith('20') and col.endswith('_CP')]

    # Ensure all identified monthly columns are numeric (redundant with previous step but good for safety)
    for col_list in [monthly_actuals_cols, monthly_forecasts_cols, monthly_plan_cols]:
        for col in col_list:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Calculate total 2025 Actuals, Forecasts, and Plans
    df['TOTAL_2025_ACTUALS'] = df[monthly_actuals_cols].sum(axis=1) if monthly_actuals_cols else 0
    df['TOTAL_2025_FORECASTS'] = df[monthly_forecasts_cols].sum(axis=1) if monthly_forecasts_cols else 0
    df['TOTAL_2025_CAPITAL_PLAN'] = df[monthly_plan_cols].sum(axis=1) if monthly_plan_cols else 0

    # Calculate Total Actuals to Date (Prior Years + 2025 Actuals)
    # Check if 'ALL_PRIOR_YEARS_ACTUALS' exists before summing
    if 'ALL_PRIOR_YEARS_ACTUALS' in df.columns:
        df['TOTAL_ACTUALS_TO_DATE'] = df['ALL_PRIOR_YEARS_ACTUALS'] + df['TOTAL_2025_ACTUALS']
    else:
        df['TOTAL_ACTUALS_TO_DATE'] = df['TOTAL_2025_ACTUALS']
        st.warning("Column 'ALL_PRIOR_YEARS_ACTUALS' not found. 'TOTAL_ACTUALS_TO_DATE' only includes 2025 actuals.")

    return df

---

# Streamlit Application

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
            "BRS_CLASSIFICATION": "Select BRS Classification"
        }

        selected_filters = {}
        for col_name, display_name in filter_columns.items():
            if col_name in df.columns:
                options = ['All'] + df[col_name].dropna().unique().tolist()
                selected_filters[col_name] = st.sidebar.selectbox(display_name, options)
            else:
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

        ---

        ## Key Metrics Overview

        col1, col2, col3, col4 = st.columns(4)

        # Use .get() with a default value for robustness in case columns are missing
        # though load_data should ensure their existence.
        with col1:
            total_business_allocation = filtered_df['BUSINESS_ALLOCATION'].sum() if 'BUSINESS_ALLOCATION' in filtered_df.columns else 0
            st.metric(label="Total Business Allocation", value=f"${total_business_allocation:,.2f}")
        with col2:
            total_current_eac = filtered_df['CURRENT_EAC'].sum() if 'CURRENT_EAC' in filtered_df.columns else 0
            st.metric(label="Total Current EAC", value=f"${total_current_eac:,.2f}")
        with col3:
            total_actuals_to_date = filtered_df['TOTAL_ACTUALS_TO_DATE'].sum() if 'TOTAL_ACTUALS_TO_DATE' in filtered_df.columns else 0
            st.metric(label="Total Actuals To Date", value=f"${total_actuals_to_date:,.2f}")
        with col4:
            total_projects = len(filtered_df)
            st.metric(label="Number of Projects", value=total_projects)

        ---

        ## Project Details

        # Define columns to display in the project details table
        project_table_cols = [
            'PORTFOLIO_OBS_LEVEL1', 'SUB_PORTFOLIO_OBS_LEVEL2', 'MASTER_PROJECT_ID',
            'PROJECT_NAME', 'PROJECT_MANAGER', 'BRS_CLASSIFICATION',
            'BUSINESS_ALLOCATION', 'CURRENT_EAC', 'ALL_PRIOR_YEARS_ACTUALS',
            'TOTAL_2025_ACTUALS', 'TOTAL_2025_FORECASTS', 'TOTAL_2025_CAPITAL_PLAN',
            'QE_FORECAST_VS_QE_PLAN', 'FORECAST_VS_BA'
        ]
        # Filter to only include columns that actually exist in the filtered_df
        project_table_cols_present = [col for col in project_table_cols if col in filtered_df.columns]

        # Define formatting for financial columns in the table
        financial_format_map = {
            col: "${:,.2f}" for col in project_table_cols_present if col in [
                'BUSINESS_ALLOCATION', 'CURRENT_EAC', 'ALL_PRIOR_YEARS_ACTUALS',
                'TOTAL_2025_ACTUALS', 'TOTAL_2025_FORECASTS', 'TOTAL_2025_CAPITAL_PLAN'
            ]
        }
        # Add specific formats for variance columns if present
        if 'QE_FORECAST_VS_QE_PLAN' in project_table_cols_present:
            financial_format_map['QE_FORECAST_VS_QE_PLAN'] = "{:,.2f}"
        if 'FORECAST_VS_BA' in project_table_cols_present:
            financial_format_map['FORECAST_VS_BA'] = "{:,.2f}"

        project_details_table = filtered_df[project_table_cols_present].style.format(financial_format_map)
        st.dataframe(project_details_table, use_container_width=True, hide_index=True)

        ---

        ## 2025 Monthly Spend Trends

        # Dynamically get monthly columns that exist in the filtered DataFrame
        monthly_actuals_cols_filtered = [col for col in filtered_df.columns if col.startswith('2025_') and col.endswith('_A')]
        monthly_forecasts_cols_filtered = [col for col in filtered_df.columns if col.startswith('2025_') and col.endswith('_F')]
        monthly_plan_cols_filtered = [col for col in filtered_df.columns if col.startswith('2025_') and col.endswith('_CP')]

        monthly_combined_df = pd.DataFrame()
        if monthly_actuals_cols_filtered or monthly_forecasts_cols_filtered or monthly_plan_cols_filtered:
            # Create data for plotting
            data_to_concat = []
            if monthly_actuals_cols_filtered:
                monthly_data_actuals = filtered_df[monthly_actuals_cols_filtered].sum().reset_index()
                monthly_data_actuals.columns = ['Month', 'Amount']
                monthly_data_actuals['Type'] = 'Actuals'
                data_to_concat.append(monthly_data_actuals)

            if monthly_forecasts_cols_filtered:
                monthly_data_forecasts = filtered_df[monthly_forecasts_cols_filtered].sum().reset_index()
                monthly_data_forecasts.columns = ['Month', 'Amount']
                monthly_data_forecasts['Type'] = 'Forecasts'
                data_to_concat.append(monthly_data_forecasts)

            if monthly_plan_cols_filtered:
                monthly_data_plan = filtered_df[monthly_plan_cols_filtered].sum().reset_index()
                monthly_data_plan.columns = ['Month', 'Amount']
                monthly_data_plan['Type'] = 'Capital Plan'
                data_to_concat.append(monthly_data_plan)

            if data_to_concat:
                monthly_combined_df = pd.concat(data_to_concat)

                # Ensure month order for plotting
                month_order = [f'2025_{i:02d}' for i in range(1, 13)]
                # Extract base month name (e.g., '2025_01' from '2025_01_A')
                monthly_combined_df['Month_Sort'] = monthly_combined_df['Month'].apply(lambda x: '_'.join(x.split('_')[:2]))
                monthly_combined_df['Month_Sort'] = pd.Categorical(monthly_combined_df['Month_Sort'], categories=month_order, ordered=True)
                monthly_combined_df = monthly_combined_df.sort_values('Month_Sort')

                fig_monthly_trends = px.line(
                    monthly_combined_df,
                    x='Month_Sort',
                    y='Amount',
                    color='Type',
                    title='Monthly Capital Trends (Actuals, Forecasts, Plan)',
                    labels={'Month_Sort': 'Month', 'Amount': 'Amount ($)'},
                    line_shape='linear',
                    markers=True
                )
                fig_monthly_trends.update_layout(hovermode="x unified", legend_title_text='Type')
                fig_monthly_trends.update_xaxes(title_text="Month (2025)")
                fig_monthly_trends.update_yaxes(title_text="Amount ($)")
                st.plotly_chart(fig_monthly_trends, use_container_width=True)
            else:
                st.warning("No 2025 monthly actuals, forecasts, or plan data found for trend analysis after filtering.")
                fig_monthly_trends = None # Explicitly set to None if no data
        else:
            st.info("No 2025 monthly actuals, forecasts, or plan columns found in the uploaded data for trend analysis.")
            fig_monthly_trends = None # Explicitly set to None if no columns

        ---

        ## Variance Analysis

        col_var1, col_var2 = st.columns(2)
        fig_qe_variance = None
        fig_ba_variance = None

        if 'QE_FORECAST_VS_QE_PLAN' in filtered_df.columns and not filtered_df['QE_FORECAST_VS_QE_PLAN'].isnull().all():
            with col_var1:
                fig_qe_variance = px.bar(
                    filtered_df,
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
                    filtered_df,
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

        ---

        ## Capital Allocation Breakdown

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

        ---

        ## Detailed Project Financials

        project_names = ['Select a Project'] + filtered_df['PROJECT_NAME'].dropna().unique().tolist()
        selected_project_name = st.selectbox("Select a project for detailed view:", project_names)

        project_details = None # Initialize to None
        fig_project_monthly = None # Initialize to None

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

            st.write("#### 2025 Monthly Breakdown:")
            # Generate monthly breakdown DataFrame dynamically based on available columns
            monthly_breakdown_data = {'Month': [f"2025_{i:02d}" for i in range(1, 13)]}
            monthly_types = {'_A': 'Actuals', '_F': 'Forecasts', '_CP': 'Capital Plan'}

            for suffix, display_name in monthly_types.items():
                col_prefix = '2025_'
                monthly_values = []
                for i in range(1, 13):
                    col_name_full = f"{col_prefix}{i:02d}{suffix}"
                    monthly_values.append(project_details.get(col_name_full, 0))
                monthly_breakdown_data[display_name] = monthly_values

            monthly_breakdown_df = pd.DataFrame(monthly_breakdown_data)

            # Format the monthly breakdown table
            monthly_format_map = {
                'Actuals': "${:,.2f}",
                'Forecasts': "${:,.2f}",
                'Capital Plan': "${:,.2f}"
            }
            st.dataframe(monthly_breakdown_df.style.format(monthly_format_map), use_container_width=True, hide_index=True)

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

        ---

        ## Generate Professional Report

        st.markdown("Click the button below to generate a comprehensive HTML report of the current dashboard view.")

        # Function to generate the HTML report content
        def generate_html_report(
            filtered_df: pd.DataFrame,
            total_business_allocation: float,
            total_current_eac: float,
            total_actuals_to_date: float,
            total_projects: int,
            monthly_combined_df: pd.DataFrame | None,
            fig_monthly_trends: px.graph_objects.Figure | None,
            fig_qe_variance: px.graph_objects.Figure | None,
            fig_ba_variance: px.graph_objects.Figure | None,
            fig_portfolio_alloc: px.graph_objects.Figure | None,
            fig_sub_portfolio_alloc: px.graph_objects.Figure | None,
            fig_brs_alloc: px.graph_objects.Figure | None,
            selected_project_name: str,
            project_details: pd.Series | None,
            fig_project_monthly: px.graph_objects.Figure | None
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
                        <div class="metric-label">Total Business Allocation</div>
                        <div class="metric-value">${total_business_allocation:,.2f}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Total Current EAC</div>
                        <div class="metric-value">${total_current_eac:,.2f}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Total Actuals To Date</div>
                        <div class="metric-value">${total_actuals_to_date:,.2f}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Number of Projects</div>
                        <div class="metric-value">{total_projects}</div>
                    </div>
                </div>

                <h2 class="section-title">Filtered Project Details</h2>
                {filtered_df[project_table_cols_present].style.format(financial_format_map).to_html(index=False)}

                <h2 class="section-title">2025 Monthly Spend Trends</h2>
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
                monthly_breakdown_data_html = {'Month': [f"2025_{i:02d}" for i in range(1, 13)]}
                for suffix, display_name in monthly_types.items():
                    col_prefix = '2025_'
                    monthly_values_html = []
                    for i in range(1, 13):
                        col_name_full_html = f"{col_prefix}{i:02d}{suffix}"
                        monthly_values_html.append(project_details.get(col_name_full_html, 0))
                    monthly_breakdown_data_html[display_name] = monthly_values_html

                monthly_breakdown_df_html = pd.DataFrame(monthly_breakdown_data_html).style.format(monthly_format_map).to_html(index=False)

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
                <h3>2025 Monthly Breakdown:</h3>
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


            report_html_content += """
                <footer>
                    <p>Generated by Capital Project Portfolio Dashboard Streamlit App.</p>
                </footer>
            </body>
            </html>
            """
            return report_html_content

        if st.button("Generate Report (HTML)"):
            # Pass all necessary variables to the report generation function
            report_content = generate_html_report(
                filtered_df, total_business_allocation, total_current_eac, total_actuals_to_date, total_projects,
                monthly_combined_df, fig_monthly_trends, fig_qe_variance, fig_ba_variance,
                fig_portfolio_alloc, fig_sub_portfolio_alloc, fig_brs_alloc,
                selected_project_name, project_details, fig_project_monthly
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

---

## View Application Source Code

with st.expander("View Application Source Code"):
    source_code = inspect.getsource(inspect.currentframe())
    st.code(source_code, language='python')
