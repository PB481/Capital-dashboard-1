import streamlit as st
import pandas as pd
import plotly.express as px
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import numpy as np
from pathlib import Path
import base64

st.set_page_config(layout="wide", page_title="Fund Analytics Dashboard")

# --- Initialize all HTML variables early to prevent NameError ---
performance_plot_html = "<i>Fund Performance Data not available.</i>"
transactions_plot_html = "<i>Transaction Data not available.</i>"
clustering_plot_html = "<i>Portfolio Holdings Data not available.</i>"
insights_html_traded = "<i>Transaction Data not available for trade volume analysis.</i>"
insights_html_complexity = "<i>Portfolio Holdings Data not available for defining security complexity.</i>"

# --- Helper Functions ---
def load_excel_data(uploaded_file, sheet_name=None):
    """Loads data from an uploaded Excel file."""
    if uploaded_file is not None:
        try:
            uploaded_file.seek(0)
            if sheet_name:
                df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
            else:
                df = pd.read_excel(uploaded_file)
            return df
        except Exception as e:
            st.error(f"Error loading data from '{uploaded_file.name}' (Sheet: '{sheet_name}'): {e}")
            return None
    return None

def generate_html_report(performance_html, transactions_html, clustering_html, insights_html):
    """Generates a simple HTML report as a byte string."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Fund Performance Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1, h2 {{ color: #333; }}
            .section {{ margin-bottom: 40px; border: 1px solid #eee; padding: 20px; border-radius: 8px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/plotly.js@latest/dist/plotly.min.js"></script>
    </head>
    <body>
        <h1>Fund Performance and Portfolio Analysis Report</h1>
        <p>Report generated on: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="section">
            <h2>1. Fund Performance</h2>
            {performance_html}
        </div>

        <div class="section">
            <h2>2. Security Transactions Analysis</h2>
            {transactions_html}
        </div>

        <div class="section">
            <h2>3. Fund Commonalities (Clustering)</h2>
            {clustering_html}
        </div>

        <div class="section">
            <h2>4. Key Insights and Analysis</h2>
            {insights_html}
        </div>

    </body>
    </html>
    """
    return html_content.encode('utf-8')

def generate_source_code_html():
    """Generates an HTML file containing the app's source code."""
    current_script_path = Path(__file__)
    try:
        with open(current_script_path, 'r') as f:
            app_code = f.read()

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>App Source Code</title>
            <style>
                body {{ font-family: 'Courier New', monospace; margin: 20px; background-color: #f6f8fa; color: #24292e; }}
                pre {{ background-color: #eef; padding: 15px; border-radius: 5px; overflow-x: auto; }}
                code {{ font-size: 0.9em; }}
                h1 {{ color: #0366d6; }}
            </style>
        </head>
        <body>
            <h1>Streamlit App Source Code</h1>
            <p>This is the Python code that builds this Streamlit application.</p>
            <pre><code>{app_code}</code></pre>
        </body>
        </html>
        """
        return html_content.encode('utf-8')
    except Exception as e:
        st.error(f"Error generating source code HTML: {e}")
        return None

# --- Main Streamlit App ---
st.title("💰 Fund Performance and Portfolio Analytics")

# --- File Upload Section ---
st.sidebar.header("Upload Data")
st.sidebar.markdown("Please upload your Excel files for analysis.")

performance_file = st.sidebar.file_uploader("Upload Fund Performance Data (Sheet: 'Performance')", type=["xlsx"])
portfolio_file = st.sidebar.file_uploader("Upload Portfolio Holdings Data (Sheet: 'Portfolio')", type=["xlsx"])
transactions_file = st.sidebar.file_uploader("Upload Transaction Data (Sheet: 'Transactions')", type=["xlsx"])

# --- Data Loading and Preprocessing ---
fund_performance_df = None
portfolio_df = None
transactions_df = None

original_performance_bytes = None
original_portfolio_bytes = None
original_transactions_bytes = None

# 1. Fund Performance Data
if performance_file:
    original_performance_bytes = performance_file.getvalue()
    fund_performance_df = load_excel_data(performance_file, sheet_name='Performance')
    if fund_performance_df is not None:
        required_cols_performance = {'ID', 'Fund Name', 'Price', 'Date'}
        if not required_cols_performance.issubset(fund_performance_df.columns):
            st.error(f"Fund Performance Data is missing required columns: {required_cols_performance - set(fund_performance_df.columns)}")
            fund_performance_df = None
        else:
            try:
                fund_performance_df['Date'] = pd.to_datetime(fund_performance_df['Date'])
                fund_performance_df = fund_performance_df.sort_values(by=['Fund Name', 'Date'])
                st.sidebar.success("Fund Performance Data Loaded!")
            except Exception as e:
                st.error(f"Error converting 'Date' column in Fund Performance Data: {e}. Please ensure 'Date' column is in a recognized date format.")
                fund_performance_df = None

# 2. Portfolio Holdings Data
if portfolio_file:
    original_portfolio_bytes = portfolio_file.getvalue()
    portfolio_df = load_excel_data(portfolio_file, sheet_name='Portfolio')
    if portfolio_df is not None:
        required_cols_portfolio = {'Fund', 'Fund IS', 'Security ID', 'Security Name', 'Industry', 'Market Value', 'Shares held'}
        if not required_cols_portfolio.issubset(portfolio_df.columns):
            st.error(f"Portfolio Holdings Data is missing required columns: {required_cols_portfolio - set(portfolio_df.columns)}")
            portfolio_df = None
        else:
            try:
                portfolio_df['Market Value'] = pd.to_numeric(portfolio_df['Market Value'], errors='coerce')
                portfolio_df['Shares held'] = pd.to_numeric(portfolio_df['Shares held'], errors='coerce')
                st.sidebar.success("Portfolio Holdings Data Loaded!")
            except Exception as e:
                st.error(f"Error converting numeric columns in Portfolio Holdings Data: {e}. Please check 'Market Value' and 'Shares held' columns.")
                portfolio_df = None

# 3. Transaction Data
if transactions_file:
    original_transactions_bytes = transactions_file.getvalue()
    transactions_df = load_excel_data(transactions_file, sheet_name='Transactions')
    if transactions_df is not None:
        required_cols_transactions = {'Fund', 'Fund ID', 'Security ID', 'Shares', 'Price', 'Base Market Value', 'Purchase or Sale'}

        actual_cols = set(transactions_df.columns)
        
        if not required_cols_transactions.issubset(actual_cols):
            st.error(f"Transaction Data is missing required columns: {required_cols_transactions - actual_cols}")
            transactions_df = None
        else:
            columns_to_keep = list(required_cols_transactions)
            transactions_df = transactions_df[columns_to_keep]

            try:
                transactions_df['Shares'] = pd.to_numeric(transactions_df['Shares'], errors='coerce')
                transactions_df['Price'] = pd.to_numeric(transactions_df['Price'], errors='coerce')
                transactions_df['Base Market Value'] = pd.to_numeric(transactions_df['Base Market Value'], errors='coerce')
                st.sidebar.success("Transaction Data Loaded!")
            except Exception as e:
                st.error(f"Error converting numeric columns in Transaction Data: {e}. Please check 'Shares', 'Price', and 'Base Market Value' columns.")
                transactions_df = None


# --- Download Uploaded Data Section in Sidebar ---
st.sidebar.markdown("---")
st.sidebar.header("Download Uploaded Files")

if original_performance_bytes:
    st.sidebar.download_button(
        label="Download Performance Excel",
        data=original_performance_bytes,
        file_name="performance_data_uploaded.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
if original_portfolio_bytes:
    st.sidebar.download_button(
        label="Download Portfolio Excel",
        data=original_portfolio_bytes,
        file_name="portfolio_data_uploaded.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
if original_transactions_bytes:
    st.sidebar.download_button(
        label="Download Transactions Excel",
        data=original_transactions_bytes,
        file_name="transactions_data_uploaded.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# --- Analysis and Visualization Sections ---

st.markdown("---")
# 1. Fund Performance Graph
st.header("1. Fund Performance Analysis")
if fund_performance_df is not None and not fund_performance_df.empty:
    selected_funds_performance = st.multiselect(
        "Select Funds for Performance Chart",
        options=fund_performance_df['Fund Name'].unique(),
        default=list(fund_performance_df['Fund Name'].unique())[:min(5, len(fund_performance_df['Fund Name'].unique()))]
    )
    if selected_funds_performance:
        filtered_performance_df = fund_performance_df[fund_performance_df['Fund Name'].isin(selected_funds_performance)]
        fig_performance = px.line(
            filtered_performance_df,
            x="Date",
            y="Price",
            color="Fund Name",
            title="Fund Performance Over Time"
        )
        st.plotly_chart(fig_performance, use_container_width=True)
        performance_plot_html = fig_performance.to_html(full_html=False, include_plotlyjs='cdn')
    else:
        st.info("Please select at least one fund to view performance.")
else:
    st.info("Please upload valid Fund Performance Data to view this section.")


st.markdown("---")
# 2. Security Transactions Analysis
st.header("2. Security Transactions Analysis")
if transactions_df is not None and not transactions_df.empty:
    transactions_df_cleaned = transactions_df.dropna(subset=['Shares', 'Price', 'Base Market Value'])

    if not transactions_df_cleaned.empty:
        st.subheader("Transactions by Share Volume")
        transaction_volume = transactions_df_cleaned.groupby(['Fund', 'Security ID'])['Shares'].sum().reset_index(name='Total_Shares').sort_values(by='Total_Shares', ascending=False)

        fig_volume = px.bar(
            transaction_volume.head(20),
            x="Security ID",
            y="Total_Shares",
            color="Fund",
            title="Top 20 Security Transactions by Share Volume (Overall)"
        )
        st.plotly_chart(fig_volume, use_container_width=True)

        st.subheader("Number of Transactions by Fund")
        transactions_by_fund = transactions_df_cleaned.groupby('Fund').size().reset_index(name='Number of Transactions')
        fig_num_transactions = px.bar(
            transactions_by_fund,
            x="Fund",
            y="Number of Transactions",
            title="Number of Transactions by Fund"
        )
        st.plotly_chart(fig_num_transactions, use_container_width=True)
        transactions_plot_html = fig_volume.to_html(full_html=False, include_plotlyjs=False) + fig_num_transactions.to_html(full_html=False, include_plotlyjs=False)
    else:
        st.warning("Transaction data became empty after cleaning missing Shares/Price values.")
        transactions_plot_html = "<i>Transaction data empty after cleaning.</i>"
else:
    st.info("Please upload valid Transaction Data to view this section.")


st.markdown("---")
# 3. Clustering Graph and Fund Commonalities
st.header("3. Fund Commonalities using Clustering")
if portfolio_df is not None and not portfolio_df.empty:
    st.markdown("This section analyzes the common relationships of funds based on their underlying portfolio holdings, industry exposure, and simulated transaction volume.")

    st.subheader("Clustering Parameters and Feature Engineering")

    portfolio_df_cleaned = portfolio_df.dropna(subset=['Market Value', 'Shares held'])
    if portfolio_df_cleaned.empty:
        st.warning("Portfolio data became empty after cleaning missing Market Value/Shares held values.")
        clustering_plot_html = "<i>Portfolio data empty after cleaning.</i>"
    else:
        fund_portfolio_agg = portfolio_df_cleaned.groupby('Fund').agg(
            Total_Market_Value=('Market Value', 'sum'),
            Unique_Securities=('Security ID', 'nunique')
        ).reset_index()

        industry_exposure = portfolio_df_cleaned.pivot_table(
            index='Fund',
            columns='Industry',
            values='Market Value',
            aggfunc='sum',
            fill_value=0
        ).fillna(0)

        clustering_df = fund_portfolio_agg.set_index('Fund').join(industry_exposure).reset_index()

        if transactions_df is not None and not transactions_df.empty:
            transactions_df_cleaned_for_cluster = transactions_df.dropna(subset=['Shares'])
            if not transactions_df_cleaned_for_cluster.empty:
                fund_transaction_volume = transactions_df_cleaned_for_cluster.groupby('Fund')['Shares'].sum().reset_index(name='Total_Shares_Traded')
                clustering_df = pd.merge(clustering_df, fund_transaction_volume, on='Fund', how='left').fillna(0)
            else:
                st.warning("Transaction data for clustering became empty after cleaning. Simulating zeros.")
                clustering_df['Total_Shares_Traded'] = 0
        else:
            st.warning("Transaction data not available for transaction volume in clustering. Simulating zeros.")
            clustering_df['Total_Shares_Traded'] = 0


        st.write("Features used for clustering:")
        st.dataframe(clustering_df.head())

        max_num_shapes = st.slider("Maximum number of fund shapes (clusters)", min_value=2, max_value=10, value=5)

        features_for_clustering = clustering_df.drop(columns=['Fund'], errors='ignore')
        numeric_features = features_for_clustering.select_dtypes(include=np.number)

        if not numeric_features.empty and len(numeric_features) >= 2:
            scaler = StandardScaler()
            scaled_features = scaler.fit_transform(numeric_features)

            n_clusters = max_num_shapes
            if n_clusters > len(scaled_features):
                st.warning(f"Number of clusters ({n_clusters}) is greater than the number of funds ({len(scaled_features)}). Adjusting clusters to number of funds.")
                n_clusters = len(scaled_features)

            if n_clusters < 2:
                st.warning("Not enough funds for clustering (requires at least 2 funds for 2 clusters).")
                clustering_plot_html = "<i>Not enough funds for clustering.</i>"
            else:
                try:
                    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                    clustering_df['Cluster'] = kmeans.fit_predict(scaled_features)

                    st.subheader("Fund Clusters (Shapes)")
                    fig_cluster = px.scatter(
                        clustering_df,
                        x="Total_Market_Value",
                        y="Unique_Securities",
                        color="Cluster",
                        hover_data=['Fund'] + list(numeric_features.columns),
                        title=f"Fund Commonalities (Clustering - {n_clusters} Shapes)"
                    )
                    st.plotly_chart(fig_cluster, use_container_width=True)
                    clustering_plot_html = fig_cluster.to_html(full_html=False, include_plotlyjs=False)

                    most_common_shape = clustering_df['Cluster'].mode()[0]
                    st.info(f"The most common fund shape (cluster) is **Cluster {most_common_shape}**.")

                    st.subheader("Funds per Cluster")
                    st.dataframe(clustering_df[['Fund', 'Cluster']].sort_values(by='Cluster'))

                    st.subheader("Cluster Characteristics")
                    cluster_summary = clustering_df.groupby('Cluster')[numeric_features.columns].mean()
                    st.dataframe(cluster_summary)
                    st.markdown("Each row above represents a 'shape' or cluster, showing the average characteristics of funds within that cluster.")
                except Exception as e:
                    st.error(f"Error during K-Means clustering: {e}")
                    clustering_plot_html = "<i>Error during clustering.</i>"
        else:
            st.warning("Not enough numeric features or funds to perform clustering. Please check your portfolio data and ensure it has at least 2 funds.")
            clustering_plot_html = "<i>Not enough data for clustering.</i>"
else:
    st.info("Please upload valid Portfolio Holdings Data to view this section.")


st.markdown("---")
# Highest and Lowest Volume of Assets Traded
st.header("Highest and Lowest Volume of Assets Traded")
if transactions_df is not None and not transactions_df.empty:
    transactions_df_cleaned = transactions_df.dropna(subset=['Shares', 'Price'])
    if not transactions_df_cleaned.empty:
        transactions_df_cleaned['Shares'] = pd.to_numeric(transactions_df_cleaned['Shares'], errors='coerce')
        transactions_df_cleaned['Price'] = pd.to_numeric(transactions_df_cleaned['Price'], errors='coerce')
        transactions_df_cleaned['Total_Value'] = transactions_df_cleaned['Shares'] * transactions_df_cleaned['Price']
        
        transactions_df_cleaned = transactions_df_cleaned.dropna(subset=['Total_Value'])

        if not transactions_df_cleaned.empty:
            top_assets_traded = transactions_df_cleaned.groupby('Security ID')['Total_Value'].sum().nlargest(10).reset_index()
            bottom_assets_traded = transactions_df_cleaned.groupby('Security ID')['Total_Value'].sum().nsmallest(10).reset_index()

            st.subheader("Top 10 Assets by Total Traded Value")
            st.dataframe(top_assets_traded)

            st.subheader("Bottom 10 Assets by Total Traded Value")
            st.dataframe(bottom_assets_traded)
            insights_html_traded = f"""
            <h3>Highest and Lowest Volume of Assets Traded</h3>
            <p><b>Top 10 Assets by Total Traded Value:</b></p>
            {top_assets_traded.to_html(index=False)}
            <p><b>Bottom 10 Assets by Total Traded Value:</b></p>
            {bottom_assets_traded.to_html(index=False)}
            """
        else:
            st.warning("Transaction data became empty after calculating 'Total_Value' due to missing or non-numeric data.")
            insights_html_traded = "<i>Transaction data empty after cleaning.</i>"
    else:
        st.warning("Transaction data became empty after cleaning for trade volume analysis (missing Shares/Price values).")
else:
    st.info("Please upload valid Transaction Data to view this section.")


st.markdown("---")
# Add Complexity to Each Security Type
st.header("Security Complexity (User Defined)")
st.markdown("Here, you can define a 'complexity score' for different security types.")

if portfolio_df is not None and not portfolio_df.empty:
    unique_industries = portfolio_df['Industry'].dropna().unique().tolist()
    if unique_industries:
        st.subheader("Define Complexity by Industry")
        complexity_scores = {}
        for industry in sorted(unique_industries):
            complexity_scores[industry] = st.slider(f"Complexity for '{industry}'", 0, 10, 5, key=f"comp_{industry}")

        portfolio_df['Security_Complexity'] = portfolio_df['Industry'].map(complexity_scores).fillna(0)

        st.subheader("Portfolio with User-Defined Security Complexity")
        st.dataframe(portfolio_df[['Fund', 'Security ID', 'Industry', 'Security_Complexity', 'Market Value', 'Shares held']].head(10))

        if all(col in portfolio_df.columns for col in ['Market Value', 'Shares held', 'Security_Complexity']) and \
           pd.api.types.is_numeric_dtype(portfolio_df['Market Value']) and \
           pd.api.types.is_numeric_dtype(portfolio_df['Shares held']) and \
           pd.api.types.is_numeric_dtype(portfolio_df['Security_Complexity']):
            fig_complexity = px.scatter(
                portfolio_df.dropna(subset=['Market Value', 'Shares held', 'Security_Complexity']),
                x="Market Value",
                y="Shares held",
                color="Security_Complexity",
                hover_data=['Fund', 'Security ID', 'Industry'],
                title="Portfolio Holdings by Market Value vs. Shares Held (Color by Complexity)"
            )
            st.plotly_chart(fig_complexity, use_container_width=True)
            insights_html_complexity = f"""
            <h3>Security Complexity (User Defined)</h3>
            <p>Security complexity scores defined by the user for various industries.</p>
            <p><b>Complexity Scores:</b> {complexity_scores}</p>
            """
        else:
            st.warning("Cannot plot security complexity due to missing or non-numeric 'Market Value', 'Shares held', or 'Security_Complexity' data.")
    else:
        st.info("No unique industries found in Portfolio Data to define complexity.")
else:
    st.info("Please upload valid Portfolio Holdings Data to define security complexity.")


st.markdown("---")
# --- HTML Report Generation & Source Code Download ---
st.sidebar.header("Generate Outputs") # Changed header for combined buttons

col_report_buttons = st.sidebar.columns(2) # Create columns in the sidebar

with col_report_buttons[0]:
    if st.button("Generate HTML Report"):
        combined_insights_html = f"""
        <h3>Key Insights:</h3>
        {insights_html_traded}
        {insights_html_complexity}
        <p><i>Further insights can be added programmatically here.</i></p>
        """
        html_report_bytes = generate_html_report(
            performance_plot_html,
            transactions_plot_html,
            clustering_plot_html,
            combined_insights_html
        )
        st.download_button(
            label="Download HTML Report",
            data=html_report_bytes,
            file_name="fund_analytics_report.html",
            mime="text/html",
            help="Download a comprehensive HTML report of the analyses."
        )
        st.sidebar.success("Report generation initiated. Click the download button!")
    else:
        st.sidebar.warning("Click to generate and download the HTML report.")

with col_report_buttons[1]:
    if st.button("Download App Source Code"):
        source_code_html_bytes = generate_source_code_html()
        if source_code_html_bytes:
            st.download_button(
                label="Download Source Code HTML",
                data=source_code_html_bytes,
                file_name="app_source_code.html",
                mime="text/html",
                help="Download the Python source code of this app as an HTML file."
            )
            st.sidebar.success("Source code generation initiated. Click the download button!")
        else:
            st.sidebar.error("Could not generate source code HTML.")
