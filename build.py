import streamlit as st
import asyncio
import threading
from src.cortex_functions import *
from snowflake.snowpark.exceptions import SnowparkSQLException
from src.notification import *
from src.utils import *
from src import rag, fine_tune  # Import RAG and Fine Tune modules
from pathlib import Path
import json

# Load the config file
config_path = Path("src/settings_config.json")
with open(config_path, "r") as f:
    config = json.load(f)

async def async_execute_functionality(session, functionality, input_data, settings, notification_id):
    """Executes the selected functionality asynchronously and updates the notification status."""
    try:
        if functionality == "Complete":
            await asyncio.sleep(1)
            get_complete_result_from_column(
                session, settings['model'], input_data['database'], input_data['schema'], input_data['table'],
                input_data['column'], settings['temperature'], settings['max_tokens'], settings['guardrails'],
                input_data['output_table'], input_data['output_column'], system_prompt=settings['system_prompt'],
                user_prompt=settings.get('user_prompt')
            )
        elif functionality == "Translate":
            await asyncio.sleep(1)
            get_translation_from_column(
                session, input_data['database'], input_data['schema'], input_data['table'], input_data['column'],
                settings['source_lang'], settings['target_lang'], input_data['output_table'], input_data['output_column']
            )
        elif functionality == "Summarize":
            await asyncio.sleep(1)
            get_summary_from_column(
                session, input_data['database'], input_data['schema'], input_data['table'], input_data['column'],
                input_data['output_table'], input_data['output_column']
            )
        elif functionality == "Extract":
            await asyncio.sleep(1)
            get_extraction_from_column(
                session, input_data['database'], input_data['schema'], input_data['table'], input_data['column'],
                input_data['query'], input_data['output_table'], input_data['output_column']
            )
        elif functionality == "Sentiment":
            await asyncio.sleep(1)
            get_sentiment_from_column(
                session, input_data['database'], input_data['schema'], input_data['table'], input_data['column'],
                input_data['output_table'], input_data['output_column']
            )

        # Update the notification to 'Success'
        update_notification_entry(session, notification_id, 'Success')
        st.success("Operation completed successfully. Check the notification screen.")
    except Exception as e:
        # Log the error and update notification to 'Failed'
        print("trying to write error")
        update_notification_entry(session, notification_id, 'Failed')
        add_log_entry(session, functionality, str(e))
        st.error("Operation failed. Check logs in the notification screen.")
        raise e

def trigger_async_operation(session, functionality, input_data, settings):
    """Trigger async operation for non-playground mode."""
    details = f"Running {functionality} on {input_data['table']} table"
    notification_id = add_notification_entry(session, functionality, 'In-Progress', details)

    # Use threading to run the async function without blocking the UI
    thread = threading.Thread(target=asyncio.run, args=(async_execute_functionality(session, functionality, input_data, settings, notification_id),))
    thread.start()

def get_functionality_settings(functionality, config):
    """Returns settings based on functionality from config."""
    settings = {}
    defaults = config["default_settings"]

    if functionality == "Complete":
        settings['model'] = st.selectbox("Change chatbot model:", defaults['model'])
        settings['temperature'] = st.slider("Temperature:", defaults['temperature_min'], defaults['temperature_max'], defaults['temperature'])
        settings['max_tokens'] = st.slider("Max Tokens:", defaults['max_tokens_min'], defaults['max_tokens_max'], defaults['max_tokens'])
        settings['guardrails'] = st.checkbox("Enable Guardrails", value=defaults['guardrails'])
        settings['system_prompt'] = st.text_area("System Prompt (optional):", placeholder="Enter a system prompt...")
        settings['user_prompt'] = st.text_input("User Prompt", placeholder="Enter a user prompt...")

    elif functionality == "Translate":
        settings['source_lang'] = st.selectbox("Source Language", defaults['languages'])
        settings['target_lang'] = st.selectbox("Target Language", defaults['languages'])

    return settings

def get_non_playground_input(session, functionality):
    """Returns input data for non-playground mode (dropdown-based)."""
    st.subheader("Select Source Table")
    
    # Database and schema selections at the same level
    col1, col2 = st.columns(2)
    database = col1.selectbox("Select Database", list_databases(session))
    schema = col2.selectbox("Select Schema", list_schemas(session, database) if database else [], disabled=not database)

    # Table and column selections at the same level
    col3, col4 = st.columns(2)
    tables = list_tables(session, database, schema) if schema else []
    selected_table = col3.selectbox("Select Table", tables if tables else ["No tables available"], disabled=not schema)
    columns = list_columns(session, database, schema, selected_table) if selected_table != "No tables available" else []
    selected_column = col4.selectbox("Select Column", columns if columns else ["No columns available"], disabled=not selected_table or selected_table == "No tables available")

    if selected_table != "No tables available" and selected_column != "No columns available":
        st.write(f"Preview of `{selected_table}`")
        table_preview = get_table_preview(session, database, schema, selected_table)
        st.dataframe(table_preview)

    # Add a text input for the query if the functionality is "Extract"
    query = None
    if functionality == "Extract":
        query = st.text_input("Enter your query for extraction:", placeholder="Type your query here...")

    st.subheader("Select Output Table and Column")
    output_table_mode = st.checkbox("Use Existing Output Table", value=True)

    col5, col6 = st.columns(2)
    if output_table_mode:
        output_tables = list_tables(session, database, schema)
        output_table = col5.selectbox("Select Output Table", output_tables if output_tables else ["No tables available"], disabled=not schema)
    else:
        output_table = col5.text_input("Enter New Output Table Name", placeholder="New output table")

    output_column = col6.text_input("Output Column Name", placeholder="Enter output column name")

    input_data = {
        'database': database,
        'schema': schema,
        'table': selected_table,
        'column': selected_column,
        'output_table': output_table,
        'output_column': output_column
    }

    if functionality == "Extract":
        input_data['query'] = query

    return input_data

def display_build(session):
    st.title("Build Mode")

    # Extend the functionality options to include RAG and Fine Tune
    functionality = st.selectbox(
        "Choose functionality:", ["Select Functionality", "Complete", "Translate", "Summarize", "Extract", "Sentiment", "RAG", "Fine Tune"]
    )

    if functionality != "Select Functionality":
        # If RAG or Fine Tune is selected, load their respective modules
        if functionality == "RAG":
            #st.subheader("Running RAG")
            rag.display_rag(session)
        elif functionality == "Fine Tune":
            #st.subheader("Running Fine Tune")
            fine_tune.display_fine_tune(session)
        else:
            # For other functionalities, continue with the existing flow
            settings = get_functionality_settings(functionality, config)
            print(settings)
            input_data = get_non_playground_input(session, functionality)

            if st.button(f"Run {functionality}"):
                try:
                    trigger_async_operation(session, functionality, input_data, settings)
                    st.success(f"Operation {functionality} triggered. Check the notifications screen for updates.")
                except SnowparkSQLException as e:
                    st.error(f"Error: {e}")