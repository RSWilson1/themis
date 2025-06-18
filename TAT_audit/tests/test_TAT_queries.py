import pytest
import os
import datetime as dt
from unittest.mock import patch, MagicMock, call # Added 'call'

# Assuming TAT_queries.py is in the TAT_audit directory
from TAT_audit.TAT_queries import Arguments
# We might need to import 'main' later for integration tests
from TAT_audit.TAT_queries import main as tat_main
# Also import the utility classes that main uses, so we can mock them.
from TAT_audit.utils import dx_requests, jira_requests, plotting, utils
# Import Jinja2 if main uses it directly, or mock where it's instantiated
from jinja2 import Environment, FileSystemLoader
import pandas as pd # Added for pd.DataFrame spec in main test
from pathlib import Path # Added for Path in main test if needed for FileSystemLoader


class TestArguments:

    @pytest.mark.parametrize("cli_args, expected_start, expected_end, expected_font_size", [
        ([], None, None, 12), # No args
        (["-s", "2023-01-01", "-e", "2023-01-31"], "2023-01-01", "2023-01-31", 12), # Start and end
        (["--start_date", "2022-12-01", "--end_date", "2022-12-15", "-f", "14"], "2022-12-01", "2022-12-15", 14), # With font size
        (["-f", "10"], None, None, 10), # Only font size
    ])
    def test_parse_args_valid(self, cli_args, expected_start, expected_end, expected_font_size, mocker):
        mocker.patch('sys.argv', ['TAT_queries.py'] + cli_args)
        # Mock methods called in Arguments.__init__ that are not the target of this test
        mocker.patch.object(Arguments, 'load_credential_info', return_value=(None,) * 10) # return tuple of Nones for 10 expected values
        mocker.patch.object(Arguments, 'determine_start_and_end_date', return_value=(None,) * 6) # return tuple of Nones for 6 expected values

        args_instance = Arguments() # parse_args is called in __init__
        # After __init__, parse_args would have been called and its result stored in self.args
        # For this test, we might need to explicitly call parse_args if __init__ structure prevents direct testing
        # However, the original code calls self.args = self.parse_args() in __init__
        # So, args_instance.args should be populated by the mocked __init__ sequence.
        # Let's ensure parse_args is called if the above mocks interfere.
        # Re-calling parse_args to ensure it's tested in isolation if __init__ is too complex with mocks:
        # args_instance.args = args_instance.parse_args() # This line might be redundant if __init__ structure is simple

        parsed_args = args_instance.args # Access the stored args

        assert parsed_args.start_date == expected_start
        assert parsed_args.end_date == expected_end
        assert parsed_args.font_size == expected_font_size

    @patch.dict(os.environ, {
        "DX_TOKEN": "fake_dx_token",
        "JIRA_EMAIL": "fake_jira_email",
        "JIRA_TOKEN": "fake_jira_token",
        "STAGING_AREA_PROJ_ID": "fake_staging_id",
        "DEFAULT_MONTHS": "3",
        "TAT_STANDARD_DAYS": "7",
        "ASSAYS": "'[\"CEN\", \"TSO500\"]'", # Note: stringified list with inner quotes
        "CANCELLED_STATUSES": "'[\"Cancelled\"]'",
        "OPEN_STATUSES": "'[\"Open\"]'",
        "LAST_JOBS": "'{\"CEN\": \"job1\", \"TSO500\": \"job2\"}'" # Note: stringified dict
    })
    def test_load_credential_info_success(self, mocker):
        # Mock sys.argv for ArgumentParser initialization if needed, though not directly testing parse_args here
        mocker.patch('sys.argv', ['TAT_queries.py'])
        args_instance = Arguments() # load_credential_info is called in __init__

        assert args_instance.dx_token == "fake_dx_token"
        assert args_instance.jira_email == "fake_jira_email"
        assert args_instance.jira_token == "fake_jira_token"
        assert args_instance.staging_id == "fake_staging_id"
        assert args_instance.default_months == "3" # Stored as string from env
        assert args_instance.tat_standard == 7     # Converted to int
        assert args_instance.assay_types == ["CEN", "TSO500"]
        assert args_instance.cancelled_statuses == ["Cancelled"]
        assert args_instance.open_statuses == ["Open"]
        assert args_instance.last_jobs == {"CEN": "job1", "TSO500": "job2"}

    @patch.dict(os.environ, {}, clear=True) # Start with empty environment
    def test_load_credential_info_missing_env_vars(self, mocker):
        mocker.patch('sys.argv', ['TAT_queries.py'])
        # Mock sys.exit to prevent test runner from exiting AND to raise SystemExit
        mock_sys_exit = mocker.patch('TAT_audit.TAT_queries.sys.exit', side_effect=SystemExit)
        # Also mock determine_start_and_end_date to prevent it from running after load_credential_info causes SystemExit
        # Use autospec=True to ensure the mock has the same signature as the original method
        mocker.patch.object(Arguments, 'determine_start_and_end_date', return_value=(None,) * 6, autospec=True)

        with pytest.raises(SystemExit): # Or check if sys.exit was called if that's preferred
             Arguments() # load_credential_info called in __init__
        mock_sys_exit.assert_called_once() # Check that sys.exit was indeed called

    @patch.dict(os.environ, { # Provide all necessary env vars for Arguments() to initialize
        "DX_TOKEN": "fake_dx_token", "JIRA_EMAIL": "fake_jira_email", "JIRA_TOKEN": "fake_jira_token",
        "STAGING_AREA_PROJ_ID": "fake_staging_id", "DEFAULT_MONTHS": "3", "TAT_STANDARD_DAYS": "7",
        "ASSAYS": "'[\"CEN\"]'", "CANCELLED_STATUSES": "'[\"Cancelled\"]'",
        "OPEN_STATUSES": "'[\"Open\"]'", "LAST_JOBS": "'{\"CEN\": \"job1\"}'"
    })
    # Removed @patch decorators, will use mocker fixture inside the function
    def test_determine_start_and_end_date(self, mocker): # Removed mock_dt_datetime_class, mock_dt_date_today from params
        # Import the module or class that uses dt, to patch it where it's used.
        # Assuming TAT_queries._dt_date and ._dt_datetime are the new targets
        import TAT_audit.TAT_queries as tat_queries_module

        # --- Scenario 1: No CLI args, use default ---
        mocker.patch('sys.argv', ['TAT_queries.py']) # No date args

        today_mock = dt.date(2023, 4, 15) # Saturday

        # Mock the _dt_date alias by replacing it with a MagicMock that has a configured 'today' method
        mock_date_class = mocker.MagicMock(spec=dt.date) # spec ensures it has date's interface
        mock_date_class.today.return_value = today_mock
        mocker.patch('TAT_audit.TAT_queries._dt_date', new=mock_date_class)

        # Mock the _dt_datetime alias by replacing it with a MagicMock that has a configured 'strptime' method
        mock_datetime_class = mocker.MagicMock(spec=dt.datetime)
        def strptime_side_effect(date_string, format_str):
            return dt.datetime.strptime(date_string, format_str) # Use real dt.datetime for conversion
        mock_datetime_class.strptime.side_effect = strptime_side_effect
        # Ensure that if the code does e.g. tat_queries_module._dt_datetime.timedelta, it still works.
        # For this, we make the mock_datetime_class delegate to the real dt.datetime for non-configured attributes.
        # This is complex. A simpler way if only strptime is used by SUT from _dt_datetime:
        # If other methods like .now() or timedelta are used directly on _dt_datetime, they also need mocking.
        # The `spec=dt.datetime` helps, but `wraps` is better for passthrough.
        # Let's try replacing _dt_datetime with a mock that has strptime, and hope no other class methods are called on _dt_datetime itself.
        mocker.patch('TAT_audit.TAT_queries._dt_datetime', new=mock_datetime_class)

        # Expected default start: 2023-04-15 minus 3 months (from DEFAULT_MONTHS env var) = 2023-01-15
        # Expected default end: 2023-04-15

        args_instance_default = Arguments() # determine_start_and_end_date is called in __init__

        assert args_instance_default.audit_start == "2023-01-15"
        assert args_instance_default.audit_end == "2023-04-15"
        assert args_instance_default.audit_start_obj == dt.datetime(2023, 1, 15) # default time is 00:00:00
        assert args_instance_default.audit_end_obj == dt.datetime(2023, 4, 15)
        assert args_instance_default.five_days_before_start == "2023-01-10" # 2023-01-15 minus 5 days
        assert args_instance_default.five_days_after == "2023-04-20"    # 2023-04-15 plus 5 days

        # --- Scenario 2: CLI args provided ---
        cli_args_provided = ["-s", "2023-03-01", "-e", "2023-03-31"]
        mocker.patch('sys.argv', ['TAT_queries.py'] + cli_args_provided)

        # Mock strptime for dt.datetime.strptime calls if they are not using the mocked dt.datetime
        # The code uses dt.datetime.strptime, so mock_dt_datetime_class.strptime should be used.
        # It's already configured with side_effect above to call the real strptime.

        args_instance_cli = Arguments()

        assert args_instance_cli.audit_start == "2023-03-01"
        assert args_instance_cli.audit_end == "2023-03-31"
        assert args_instance_cli.audit_start_obj == dt.datetime(2023, 3, 1)
        assert args_instance_cli.audit_end_obj == dt.datetime(2023, 3, 31)
        assert args_instance_cli.five_days_before_start == "2023-02-24" # 2023-03-01 minus 5 days
        assert args_instance_cli.five_days_after == "2023-04-05"    # 2023-03-31 plus 5 days

    @patch.dict(os.environ, { # Provide all necessary env vars for Arguments() to initialize
        "DX_TOKEN": "fake_dx_token", "JIRA_EMAIL": "fake_jira_email", "JIRA_TOKEN": "fake_jira_token",
        "STAGING_AREA_PROJ_ID": "fake_staging_id", "DEFAULT_MONTHS": "3", "TAT_STANDARD_DAYS": "7",
        "ASSAYS": "'[\"CEN\"]'", "CANCELLED_STATUSES": "'[\"Cancelled\"]'",
        "OPEN_STATUSES": "'[\"Open\"]'", "LAST_JOBS": "'{\"CEN\": \"job1\"}'"
    })
    @pytest.mark.parametrize("cli_args, error_message_match", [
        (["-s", "2023-01-01"], "must be given together"), # Only start_date
        (["-e", "2023-01-31"], "must be given together"), # Only end_date
        (["-s", "2023-02-01", "-e", "2023-01-01"], "must be before --end_date"), # Start after end
    ])
    def test_determine_start_and_end_date_invalid_cli(self, cli_args, error_message_match, mocker):
        import TAT_audit.TAT_queries as tat_queries_module
        mocker.patch('sys.argv', ['TAT_queries.py'] + cli_args)

        # Mock datetime objects to prevent errors if default date logic is touched
        today_mock = dt.date(2023, 1, 1) # A fixed date for any today() calls

        mock_date_class_invalid = mocker.MagicMock(spec=dt.date)
        mock_date_class_invalid.today.return_value = today_mock
        mocker.patch('TAT_audit.TAT_queries._dt_date', new=mock_date_class_invalid)

        mock_datetime_class_invalid = mocker.MagicMock(spec=dt.datetime)
        mock_datetime_class_invalid.strptime.side_effect = lambda date_str, fmt: dt.datetime.strptime(date_str, fmt)
        mocker.patch('TAT_audit.TAT_queries._dt_datetime', new=mock_datetime_class_invalid)

        with pytest.raises(RuntimeError, match=error_message_match):
            Arguments() # determine_start_and_end_date is called in __init__

# It's good practice to keep a backup of original datetime objects if they are widely mocked
# _real_dt_datetime = dt.datetime
# _real_dt_date = dt.date

class TestMainFunction:

    @patch('TAT_audit.TAT_queries.Arguments') # Mock the Arguments class
    @patch('TAT_audit.TAT_queries.DXFunctions') # Mock DXFunctions where it's used by main
    @patch('TAT_audit.TAT_queries.JiraFunctions') # Mock JiraFunctions
    @patch('TAT_audit.TAT_queries.GeneralFunctions') # Mock GeneralFunctions
    @patch('TAT_audit.TAT_queries.PlottingFunctions') # Mock PlottingFunctions
    @patch('TAT_audit.TAT_queries.Environment') # Mock Jinja Environment
    @patch('builtins.open') # Mock open for file writing
    @patch('TAT_audit.TAT_queries.pd.DataFrame.to_csv') # Mock to_csv if main calls it directly on a DataFrame
    @patch('TAT_audit.TAT_queries.logger') # Mock the logger used in main
    def test_main_function_orchestration(
        self, mock_logger, mock_df_to_csv, mock_builtin_open, mock_jinja_env,
        mock_plotting_cls, mock_general_cls, mock_jira_cls, mock_dx_cls, mock_arguments_cls,
        mocker # For any other ad-hoc mocks
    ):
        # --- 1. Setup Mocks ---

        # Mock instance of Arguments and its attributes
        mock_args_instance = MagicMock()
        mock_args_instance.dx_token = "mock_dx_token"
        mock_args_instance.jira_email = "mock_jira_email"
        mock_args_instance.jira_token = "mock_jira_token"
        mock_args_instance.staging_id = "mock_staging_id"
        mock_args_instance.default_months = "1"
        mock_args_instance.tat_standard = 7
        mock_args_instance.assay_types = ["CEN"]
        mock_args_instance.cancelled_statuses = ["Cancelled"]
        mock_args_instance.open_statuses = ["Open"]
        mock_args_instance.last_jobs = {"CEN": "final_job_cen"}
        mock_args_instance.audit_start = "2023-01-01"
        mock_args_instance.audit_end = "2023-01-31"
        mock_args_instance.audit_start_obj = dt.datetime(2023,1,1)
        mock_args_instance.audit_end_obj = dt.datetime(2023,1,31)
        mock_args_instance.five_days_before_start = "2022-12-27"
        mock_args_instance.five_days_after = "2023-02-05"
        mock_args_instance.args = MagicMock(font_size=12) # Mock the nested args attribute for font_size

        mock_arguments_cls.return_value = mock_args_instance

        # Mock instances of utility classes
        mock_dx_instance = MagicMock(spec=dx_requests.DXFunctions)
        mock_dx_cls.return_value = mock_dx_instance

        mock_jira_instance = MagicMock(spec=jira_requests.JiraFunctions)
        mock_jira_cls.return_value = mock_jira_instance

        mock_general_instance = MagicMock(spec=utils.GeneralFunctions)
        mock_general_cls.return_value = mock_general_instance

        mock_plotting_instance = MagicMock(spec=plotting.PlottingFunctions)
        mock_plotting_cls.return_value = mock_plotting_instance

        # Mock Jinja Environment and template
        mock_template = MagicMock()
        mock_template.render.return_value = "<html>mocked report</html>"
        mock_jinja_env_instance = MagicMock()
        mock_jinja_env_instance.get_template.return_value = mock_template
        mock_jinja_env.return_value = mock_jinja_env_instance

        # --- 2. Define mock return values for utility methods ---
        # DXFunctions
        mock_dx_instance.get_002_projects_within_buffer_period.return_value = [{"id": "proj1", "describe": {"name": "002_230115_RUN001_CEN"}}] # Sample project
        mock_dx_instance.create_run_dictionary.return_value = {"RUN001": {"project_id": "proj1", "assay_type": "CEN"}}
        mock_dx_instance.get_staging_folders.return_value = ["RUN001_folder"]
        # add_upload_time returns the modified dict
        mock_dx_instance.add_upload_time.return_value = {"RUN001": {"project_id": "proj1", "assay_type": "CEN", "upload_time": "2023-01-15 10:00:00"}}
        # update_run_name returns (dict, list_of_typos)
        mock_dx_instance.update_run_name.return_value = ({"RUN001": {"project_id": "proj1", "assay_type": "CEN", "upload_time": "2023-01-15 10:00:00"}}, [])
        mock_dx_instance.find_conductor_jobs.return_value = [{"describe": {"name": "conductor-RUN001", "created": 1673776800000}}] # 2023-01-15 10:00:00
        mock_dx_instance.get_earliest_conductor_job_for_each_run.return_value = {"RUN001": 1673776800.0}
        # add_first_job_time returns the modified dict
        mock_dx_instance.add_first_job_time.return_value = {"RUN001": {"project_id": "proj1", "assay_type": "CEN", "upload_time": "2023-01-15 10:00:00", "first_job": "2023-01-15 10:00:00"}}
        # add_last_job_time returns the modified dict
        mock_dx_instance.add_last_job_time.return_value = {"RUN001": {"project_id": "proj1", "assay_type": "CEN", "upload_time": "2023-01-15 10:00:00", "first_job": "2023-01-15 10:00:00", "processing_finished": "2023-01-16 10:00:00"}}

        # JiraFunctions
        # query_jira_tickets_in_queue can be called twice
        mock_jira_instance.query_jira_tickets_in_queue.side_effect = [
            [{"fields": {"summary": "RUN001", "created": "2023-01-15T10:00:00.000Z", "status": {"name": "All samples released"}, "customfield_10070": [{"value": "CEN"}], "key": "JIRA-1", "id": "123"}}], # Closed queue
            [] # Open queue (empty)
        ]
        mock_jira_instance.create_jira_info_dict.return_value = {"RUN001": {"ticket_key": "JIRA-1", "ticket_id": "123", "jira_status": "All samples released", "assay_type": "CEN", "date_jira_ticket_created": dt.datetime(2023,1,15,10,0,0)}}
        # add_jira_ticket_info returns (dict, typo_tickets, runs_no_002_proj, cancelled_runs, open_runs_list)
        mock_jira_instance.add_jira_ticket_info.return_value = (
            {"RUN001": {"project_id": "proj1", "assay_type": "CEN", "upload_time": "2023-01-15 10:00:00", "first_job": "2023-01-15 10:00:00", "processing_finished": "2023-01-16 10:00:00", "ticket_key": "JIRA-1", "ticket_id": "123", "jira_status": "All samples released"}},
            [], [], [], []
        )
        # add_transition_times returns the modified dict
        mock_jira_instance.add_transition_times.return_value = {"RUN001": {"project_id": "proj1", "assay_type": "CEN", "upload_time": "2023-01-15 10:00:00", "first_job": "2023-01-15 10:00:00", "processing_finished": "2023-01-16 10:00:00", "ticket_key": "JIRA-1", "ticket_id": "123", "jira_status": "All samples released", "jira_resolved": "2023-01-17 10:00:00"}}

        # GeneralFunctions
        # add_in_empty_keys returns the modified dict
        mock_general_instance.add_in_empty_keys.return_value = {"RUN001": {"project_id": "proj1", "assay_type": "CEN", "upload_time": "2023-01-15 10:00:00", "first_job": "2023-01-15 10:00:00", "processing_finished": "2023-01-16 10:00:00", "ticket_key": "JIRA-1", "ticket_id": "123", "jira_status": "All samples released", "jira_resolved": "2023-01-17 10:00:00"}}
        # create_run_df returns a DataFrame
        mock_run_df = MagicMock(spec=pd.DataFrame) # Use a MagicMock for DataFrame to avoid needing real data
        mock_run_df.empty = False # Simulate it's not empty
        mock_general_instance.create_run_df.return_value = mock_run_df
        mock_general_instance.add_jira_ticket_hyperlink.return_value = mock_run_df # Returns modified df
        mock_general_instance.add_run_week.return_value = mock_run_df # Returns modified df
        mock_general_instance.create_typo_df.side_effect = [None, None] # For typo_002_list and typo_tickets
        mock_general_instance.add_calculation_columns.return_value = mock_run_df # Returns modified df
        # create_assay_objects returns (assay_df, assay_stats, assay_issues, assay_runs, assay_frac, assay_compl)
        mock_general_instance.create_assay_objects.return_value = (MagicMock(spec=pd.DataFrame), "stats_html", {}, 1, "1/1", 100.0)
        mock_general_instance.add_in_cancelled_runs.return_value = mock_run_df # Returns modified df

        # PlottingFunctions
        mock_plotting_instance.create_both_figures.return_value = ("<fig_html>", "<upload_fig_html>")

        # --- 3. Call main function ---
        tat_main()

        # --- 4. Assertions ---
        # Check Arguments class was instantiated
        mock_arguments_cls.assert_called_once()

        # Check DXFunctions methods
        mock_dx_instance.login.assert_called_once_with(mock_args_instance.dx_token)
        mock_dx_instance.get_002_projects_within_buffer_period.assert_called_once()
        mock_dx_instance.create_run_dictionary.assert_called_once()
        # ... (add more assertions for other DXFunctions calls if critical)

        # Check JiraFunctions instantiation and methods
        mock_jira_cls.assert_called_once_with(
            mock_args_instance.jira_email, mock_args_instance.jira_token, mock_args_instance.assay_types,
            mock_args_instance.cancelled_statuses, mock_args_instance.audit_start_obj,
            mock_args_instance.audit_end_obj, mock_args_instance.open_statuses,
            mock_args_instance.five_days_before_start, mock_args_instance.five_days_after
        )
        assert mock_jira_instance.query_jira_tickets_in_queue.call_count == 2 # Called for closed and open queues
        mock_jira_instance.create_jira_info_dict.assert_called_once()
        # ... (add more assertions for other JiraFunctions calls)

        # Check GeneralFunctions instantiation and methods
        mock_general_cls.assert_called_once_with(
            mock_args_instance.tat_standard, mock_args_instance.cancelled_statuses,
            mock_args_instance.open_statuses, mock_args_instance.audit_start, mock_args_instance.audit_end
        )
        mock_general_instance.create_run_df.assert_called_once()
        mock_general_instance.write_to_csv.assert_called_once_with(mock_run_df) # Check it's called with the df

        # Check PlottingFunctions instantiation and methods
        mock_plotting_cls.assert_called_once_with(
            mock_args_instance.cancelled_statuses, mock_args_instance.audit_start,
            mock_args_instance.audit_end, mock_args_instance.tat_standard, mock_args_instance.args.font_size
        )
        mock_plotting_instance.create_both_figures.assert_called_once() # For "CEN" assay

        # Check Jinja2 environment and template rendering
        # The path for FileSystemLoader might be tricky, ensure it matches TAT_queries.py
        # It uses ROOT_DIR.joinpath("templates") which is TAT_audit/templates
        # We can assert that the path used in FileSystemLoader is correct if ROOT_DIR is consistent
        # For simplicity, just check it was called.
        mock_jinja_env.assert_called_once()
        # Example of how to check FileSystemLoader path if ROOT_DIR can be determined/mocked:
        # expected_template_path = Path(TAT_audit_module_path_if_known) / "templates"
        # mock_jinja_env.assert_called_once_with(loader=FileSystemLoader(expected_template_path_str))

        mock_jinja_env_instance.get_template.assert_called_once_with("audit_template.html")
        mock_template.render.assert_called_once() # Check that render was called

        # Check file writing for HTML report
        expected_html_filename = f"turnaround_times_{mock_args_instance.audit_start}_{mock_args_instance.audit_end}.html"
        mock_builtin_open.assert_any_call(expected_html_filename, mode="w", encoding="utf-8")

        # Check that the logger was used (optional, but good for completeness)
        mock_logger.info.assert_any_call("Creating a run dict for all assays")
        # ... (add more logger call checks if desired)
