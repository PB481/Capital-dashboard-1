import streamlit as st
import pandas as pd
from pathlib import Path
import datetime
import altair as alt # Import Altair for chart generation in HTML report

# Set the title and favicon that appear in the Browser's tab bar.
st.set_page_config(
    page_title='Capital and Budget Monitoring Tool',
    page_icon=':chart_with_upwards_trend:',
    layout='wide' # Use wide layout for better display
)

# -----------------------------------------------------------------------------
# Declare some useful functions.

@st.cache_data
def load_project_data(uploaded_file):
    """Loads project data from an uploaded CSV file.

    Assumes the CSV has columns: 'Project Name', 'Date', 'Budget', 'Actual Spend'.
    The 'Date' column will be converted to datetime objects.
    """
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        # Ensure essential columns exist
        required_columns = ['Project Name', 'Date', 'Budget', 'Actual Spend']
        if not all(col in df.columns for col in required_columns):
            st.error(f"The uploaded CSV must contain the following columns: {', '.join(required_columns)}")
            return pd.DataFrame() # Return an empty DataFrame if columns are missing

        df['Date'] = pd.to_datetime(df['Date'])
        return df
    return pd.DataFrame() # Return an empty DataFrame if no file is uploaded

def generate_html_report(filtered_df, summary_df, chart_object, from_date, to_date):
    """Generates an HTML report string from the app's data and visualizations."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Capital and Budget Report ({from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')})</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1, h2, h3 {{ color: #333; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .red-text {{ color: red; font-weight: bold; }}
            .green-text {{ color: green; font-weight: bold; }}
            .chart-container {{ width: 100%; overflow-x: auto; }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/vega@{alt.VEGA_VERSION}" charset="utf-8"></script>
        <script src="https://cdn.jsdelivr.net/npm/vega-lite@{alt.VEGALITE_VERSION}" charset="utf-8"></script>
        <script src="https://cdn.jsdelivr.net/npm/vega-embed@{alt.VEGAEMBED_VERSION}" charset="utf-8"></script>
    </head>
    <body>
        <h1>Capital and Budget Monitoring Report</h1>
        <p>Report generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Date Range: {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}</p>

        <h2>1. Filtered Project Data</h2>
        {filtered_df.to_html(index=False)}

        <h2>2. Budget vs Actual Spend Over Time</h2>
        <div id="chart" class="chart-container"></div>
        <script type="text/javascript">
            var spec = {chart_object.to_json(indent=None)};
            vegaEmbed('#chart', spec, {{mode: "vega-lite"}}).catch(console.error);
        </script>

        <h2>3. Project Performance Summary</h2>
        {summary_df.to_html(index=False, float_format='%.2f')}

        <h3>Projects over 10% or under -10% of budget:</h3>
        <ul>
    """

    highlighted_projects = summary_df[
        (summary_df['Percentage_Deviation'] > 10) | (summary_df['Percentage_Deviation'] < -10)
    ]

    if not highlighted_projects.empty:
        for index, row in highlighted_projects.iterrows():
            project_name = row['Project Name']
            deviation = row['Percentage_Deviation']
            total_budget = row['Total_Budget']
            total_actual = row['Total_Actual']

            if deviation > 10:
                html_content += f"""
                <li><span class="red-text">{project_name}</span>: Actual Spend: ${total_actual:,.2f} (Over budget by {deviation:.2f}%)</li>
                """
            elif deviation < -10:
                html_content += f"""
                <li><span class="green-text">{project_name}</span>: Actual Spend: ${total_actual:,.2f} (Under budget by {abs(deviation):.2f}%)</li>
                """
    else:
        html_content += "<li>No projects are currently over or under 10% of their budget for the selected period.</li>"

    html_content += """
        </ul>
    </body>
    </html>
    """
    return html_content


# -----------------------------------------------------------------------------
# Draw the actual page

st.title(':chart_with_upwards_trend: Capital and Budget Monitoring Tool')

st.markdown("Upload your project budget and actual spend data to visualize and monitor your projects.")

''
''

uploaded_file = st.file_uploader("Upload your project data CSV", type=["csv"])

project_df = load_project_data(uploaded_file)

if not project_df.empty:
    min_date_pd = project_df['Date'].min()
    max_date_pd = project_df['Date'].max()

    min_date = min_date_pd.date()
    max_date = max_date_pd.date()

    from_date, to_date = st.slider(
        'Select the date range:',
        min_value=min_date,
        max_value=max_date,
        value=[min_date, max_date],
        format="YYYY-MM-DD"
    )

    projects = project_df['Project Name'].unique()

    if not len(projects):
        st.warning("No projects found in the uploaded data.")
    else:
        selected_projects = st.multiselect(
            'Which projects would you like to view?',
            projects,
            projects
        )

        ''
        ''
        ''

        filtered_project_df = project_df[
            (project_df['Project Name'].isin(selected_projects))
            & (project_df['Date'].dt.date >= from_date)
            & (project_df['Date'].dt.date <= to_date)
        ]

        st.header('Budget vs Actual Spend Over Time', divider='gray')

        if filtered_project_df.empty:
            st.info("No data available for the selected projects and date range. Please adjust your selections or upload more data.")
            chart_for_report = None # No chart if no data
            summary_df = pd.DataFrame() # Empty summary
        else:
            # Calculate the deviation and create the combined label
            chart_df = filtered_project_df.copy() # Start with the full filtered df
            chart_df['Deviation'] = chart_df['Actual Spend'] - chart_df['Budget']
            chart_df['Project_Date_Label'] = chart_df['Project Name'] + ' - ' + chart_df['Date'].dt.strftime('%Y-%m-%d')

            # Create Altair chart for both display and report
            chart = alt.Chart(chart_df).mark_bar().encode(
                x=alt.X('Project_Date_Label:N', sort=None, title='Project - Date'),
                y=alt.Y('Deviation:Q', title='Amount (Actual - Budget)', axis=alt.Axis(format='$,.2f')),
                color=alt.condition(
                    alt.datum.Deviation > 0,
                    alt.value('red'),  # Over budget
                    alt.value('green') # Under budget
                ),
                tooltip=[
                    'Project Name',
                    alt.Tooltip('yearmonthdate(Date)', title='Date'),
                    alt.Tooltip('Budget', format='$,.2f'),
                    alt.Tooltip('Actual Spend', format='$,.2f'),
                    alt.Tooltip('Deviation', format='$,.2f', title='Deviation')
                ]
            ).properties(
                title='Budget vs Actual Spend Deviation by Project and Date'
            ).interactive()

            st.altair_chart(chart, use_container_width=True)
            chart_for_report = chart # Assign chart object for report generation

            st.header('Project Performance Summary', divider='gray')

            summary_df = filtered_project_df.groupby('Project Name').agg(
                Total_Budget=('Budget', 'sum'),
                Total_Actual=('Actual Spend', 'sum')
            ).reset_index()

            summary_df['Percentage_Deviation'] = summary_df.apply(
                lambda row: ((row['Total_Actual'] - row['Total_Budget']) / row['Total_Budget']) * 100
                if row['Total_Budget'] != 0 else float('inf') if row['Total_Actual'] > 0 else 0,
                axis=1
            )

            st.write("Projects that are **over 10%** or **under -10%** of budget:")

            highlighted_projects = summary_df[
                (summary_df['Percentage_Deviation'] > 10) | (summary_df['Percentage_Deviation'] < -10)
            ]

            if not highlighted_projects.empty:
                for index, row in highlighted_projects.iterrows():
                    project_name = row['Project Name']
                    deviation = row['Percentage_Deviation']
                    total_budget = row['Total_Budget']
                    total_actual = row['Total_Actual']

                    if deviation > 10:
                        st.markdown(
                            f"<p style='color:red;'>**{project_name}**: Actual Spend: ${total_actual:,.2f} (Over budget by {deviation:.2f}%)</p>",
                            unsafe_allow_html=True
                        )
                    elif deviation < -10:
                        st.markdown(
                            f"<p style='color:green;'>**{project_name}**: Actual Spend: ${total_actual:,.2f} (Under budget by {abs(deviation):.2f}%)</p>",
                            unsafe_allow_html=True
                        )
            else:
                st.info("No projects are currently over or under 10% of their budget for the selected period.")

        # --- Download Buttons ---
        st.markdown("---")
        st.header('Download Data & Report', divider='gray')

        col1, col2 = st.columns(2)

        with col1:
            # Download filtered data
            csv_data = filtered_project_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Filtered Data as CSV",
                data=csv_data,
                file_name="filtered_project_data.csv",
                mime="text/csv",
                help="Download the data currently displayed in the tables above."
            )

        with col2:
            if chart_for_report is not None and not filtered_project_df.empty:
                html_report_content = generate_html_report(filtered_project_df, summary_df, chart_for_report, from_date, to_date)
                st.download_button(
                    label="Generate HTML Report",
                    data=html_report_content.encode('utf-8'),
                    file_name=f"Capital_Budget_Report_{from_date.strftime('%Y%m%d')}_to_{to_date.strftime('%Y%m%d')}.html",
                    mime="text/html",
                    help="Generate a comprehensive HTML report of the selected data and charts."
                )
            else:
                st.info("Upload data and select projects/dates to enable HTML report generation.")

else:
    st.info("Please upload a CSV file to get started.")
    chart_for_report = None # No chart if no data
    summary_df = pd.DataFrame() # Empty summary

# --- Feature: Show App Code ---
st.markdown("---") # Add a separator
st.header('App Source Code', divider='gray')

current_script_path = Path(__file__)

try:
    with open(current_script_path, 'r') as f:
        app_code = f.read()
    with st.expander("Click to view the Python code for this app"):
        st.code(app_code, language='python')
except Exception as e:
    st.error(f"Could not load app source code: {e}")
