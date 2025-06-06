import streamlit as st
import pandas as pd
from pathlib import Path
import datetime # Import the datetime module

# Set the title and favicon that appear in the Browser's tab bar.
st.set_page_config(
    page_title='Capital and Budget Monitoring Tool',
    page_icon=':chart_with_upwards_trend:', # A new emoji icon
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

# -----------------------------------------------------------------------------
# Draw the actual page

'''
# :chart_with_upwards_trend: Capital and Budget Monitoring Tool

Upload your project budget and actual spend data to visualize and monitor your projects.
'''

''
''

uploaded_file = st.file_uploader("Upload your project data CSV", type=["csv"])

project_df = load_project_data(uploaded_file)

if not project_df.empty:
    min_date_pd = project_df['Date'].min()
    max_date_pd = project_df['Date'].max()

    # Convert pandas Timestamps to Python datetime.date objects for the slider
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
            projects # Default to selecting all projects
        )

        ''
        ''
        ''

        # Filter the data
        filtered_project_df = project_df[
            (project_df['Project Name'].isin(selected_projects))
            & (project_df['Date'].dt.date >= from_date) # Convert to date part for comparison
            & (project_df['Date'].dt.date <= to_date)   # Convert to date part for comparison
        ]

        st.header('Budget vs Actual Spend Over Time', divider='gray')

        if filtered_project_df.empty:
            st.info("No data available for the selected projects and date range. Please adjust your selections or upload more data.")
        else:
            # Prepare data for plotting: melt 'Budget' and 'Actual Spend' into 'Value' for consistent plotting
            chart_df = filtered_project_df.melt(
                id_vars=['Project Name', 'Date'],
                value_vars=['Budget', 'Actual Spend'],
                var_name='Type',
                value_name='Amount'
            )

            st.line_chart(
                chart_df,
                x='Date',
                y='Amount',
                color='Type',
                use_container_width=True
            )

            st.header('Project Performance Summary', divider='gray')

            # Calculate and display under/over budget projects
            summary_df = filtered_project_df.groupby('Project Name').agg(
                Total_Budget=('Budget', 'sum'),
                Total_Actual=('Actual Spend', 'sum')
            ).reset_index()

            # Handle division by zero for projects with 0 budget
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

else:
    st.info("Please upload a CSV file to get started.")

# --- Feature: Show App Code ---
st.markdown("---") # Add a separator
st.header('App Source Code', divider='gray')

# Get the path to the current script
# Using Path(__file__) is robust for finding the script's own path
current_script_path = Path(__file__)

try:
    with open(current_script_path, 'r') as f:
        app_code = f.read()
    with st.expander("Click to view the Python code for this app"):
        st.code(app_code, language='python')
except Exception as e:
    st.error(f"Could not load app source code: {e}")
