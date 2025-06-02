import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, call
import datetime as dt

from TAT_audit.utils.utils import GeneralFunctions

@pytest.fixture
def general_functions_instance():
    return GeneralFunctions(
        tat_standard=7,
        cancelled_statuses=["Cancelled", "Data not received"],
        open_statuses=["Open", "On Hold"],
        audit_start="2023-01-01",
        audit_end="2023-01-31"
    )

@pytest.fixture
def sample_run_dict():
    return {
        "RUN001": {
            "assay_type": "CEN", "upload_time": "2023-01-05 10:00:00", 
            "first_job": "2023-01-05 11:00:00", "processing_finished": "2023-01-07 12:00:00",
            "jira_status": "All samples released", "jira_resolved": "2023-01-08 10:00:00",
            "change_log": {"some_log": "some_time"}, "ticket_key": "KEY-001"
        },
        "RUN002_MISSING_KEYS": { # Some keys missing
            "assay_type": "TSO500", "upload_time": "2023-01-06 09:00:00",
            "ticket_key": "KEY-002"
            # Missing first_job, processing_finished, jira_status, jira_resolved, change_log
        }
    }

@pytest.fixture
def sample_run_df(sample_run_dict):
    # A simplified version of what create_run_df would produce, for other tests
    gf = GeneralFunctions(7, [], [], "2023-01-01", "2023-01-31")
    # Add missing keys first to avoid issues in create_run_df
    run_dict_full_keys = gf.add_in_empty_keys(sample_run_dict)
    return gf.create_run_df(run_dict_full_keys)


class TestGeneralFunctions:

    def test_init(self):
        tat_standard = 5
        cancelled_statuses = ["S1"]
        open_statuses = ["S2"]
        audit_start = "2022-01-01"
        audit_end = "2022-12-31"
        
        gf = GeneralFunctions(tat_standard, cancelled_statuses, open_statuses, audit_start, audit_end)
        
        assert gf.tat_standard == tat_standard
        assert gf.cancelled_statuses == cancelled_statuses
        assert gf.open_statuses == open_statuses
        assert gf.audit_start == audit_start
        assert gf.audit_end == audit_end

    def test_add_in_empty_keys(self, general_functions_instance, sample_run_dict):
        """Test that missing essential keys are added as None."""
        # sample_run_dict already has RUN002_MISSING_KEYS
        run_dict_input = sample_run_dict.copy() # Operate on a copy
        
        # Expected keys to be added if missing
        keys_to_add = [
            'upload_time', 'first_job', 'processing_finished', 'jira_status',
            'jira_resolved', 'change_log', 'ticket_key'
        ]
        
        result_dict = general_functions_instance.add_in_empty_keys(run_dict_input)
        
        # Check RUN001 (should be largely untouched if keys were present)
        for key in keys_to_add:
            assert key in result_dict["RUN001"] 
        
        # Check RUN002_MISSING_KEYS
        assert result_dict["RUN002_MISSING_KEYS"]["assay_type"] == "TSO500" # Existing key
        assert result_dict["RUN002_MISSING_KEYS"]["upload_time"] == "2023-01-06 09:00:00" # Existing
        assert result_dict["RUN002_MISSING_KEYS"]["ticket_key"] == "KEY-002" # Existing

        assert result_dict["RUN002_MISSING_KEYS"]["first_job"] is None
        assert result_dict["RUN002_MISSING_KEYS"]["processing_finished"] is None
        assert result_dict["RUN002_MISSING_KEYS"]["jira_status"] is None
        assert result_dict["RUN002_MISSING_KEYS"]["jira_resolved"] is None
        assert result_dict["RUN002_MISSING_KEYS"]["change_log"] is None
        
        # Test with a run that has all keys initially missing
        run_all_missing = {"RUN003_ALL_MISSING": {"assay_type": "MYE"}}
        result_all_missing = general_functions_instance.add_in_empty_keys(run_all_missing)
        for key in keys_to_add:
            if key == 'assay_type': continue # This one was provided
            assert result_all_missing["RUN003_ALL_MISSING"][key] is None


    def test_create_run_df(self, general_functions_instance, sample_run_dict):
        """Test creation of the main DataFrame from the run dictionary."""
        # Ensure keys are present before creating df, as actual function relies on add_in_empty_keys being called prior implicitly
        run_dict_full = general_functions_instance.add_in_empty_keys(sample_run_dict.copy())
        
        df = general_functions_instance.create_run_df(run_dict_full)
        
        assert isinstance(df, pd.DataFrame)
        assert "run_name" in df.columns
        assert len(df) == 2
        assert df.iloc[0]["run_name"] == "RUN001" # or RUN002 depending on dict iteration order
        assert df.iloc[1]["run_name"] == "RUN002_MISSING_KEYS"
        
        expected_cols = [
            'assay_type', 'run_name', 'upload_time', 'first_job',
            'processing_finished', 'jira_status', 'jira_resolved',
            'change_log', 'ticket_key'
        ]
        assert all(col in df.columns for col in expected_cols)
        
        # Check dtypes for datetime columns
        datetime_cols = ['upload_time', 'first_job', 'processing_finished', 'jira_resolved']
        for col in datetime_cols:
            # NaT is also a valid datetime object for missing values
            assert pd.api.types.is_datetime64_any_dtype(df[col])
            
        # Check specific values for RUN001
        run001_data = df[df["run_name"] == "RUN001"].iloc[0]
        assert run001_data["upload_time"] == pd.Timestamp("2023-01-05 10:00:00")
        assert run001_data["change_log"] == {"some_log": "some_time"}
        
        # Check specific values for RUN002 (where many were None)
        run002_data = df[df["run_name"] == "RUN002_MISSING_KEYS"].iloc[0]
        assert pd.isna(run002_data["first_job"])
        assert pd.isna(run002_data["jira_status"])


    def test_create_run_df_empty_dict(self, general_functions_instance, mocker):
        """Test create_run_df with an empty input dictionary."""
        # Mock sys.exit to prevent test runner from exiting
        mock_sys_exit = mocker.patch('TAT_audit.utils.utils.sys.exit')
        
        with pytest.raises(SystemExit): # As the code sys.exits
             general_functions_instance.create_run_df({})
        mock_sys_exit.assert_called_once_with(1)


    def test_generate_hyperlink(self, general_functions_instance):
        """Test Jira ticket hyperlink generation."""
        row_data = pd.Series({
            'ticket_key': 'KEY-123',
            'run_name': 'RUN_ABC'
        })
        expected_link = '<a href="https://cuhbioinformatics.atlassian.net/browse/KEY-123">RUN_ABC</a>'
        assert general_functions_instance.generate_hyperlink(row_data) == expected_link

    def test_add_jira_ticket_hyperlink(self, general_functions_instance, sample_run_df):
        """Test adding the 'ticket_hyperlink' column to the DataFrame."""
        df_with_hyperlinks = general_functions_instance.add_jira_ticket_hyperlink(sample_run_df.copy())
        
        assert "ticket_hyperlink" in df_with_hyperlinks.columns
        
        run001_link = df_with_hyperlinks[df_with_hyperlinks["run_name"] == "RUN001"].iloc[0]["ticket_hyperlink"]
        assert run001_link == '<a href="https://cuhbioinformatics.atlassian.net/browse/KEY-001">RUN001</a>'
        
        # RUN002 has a ticket_key KEY-002
        run002_link = df_with_hyperlinks[df_with_hyperlinks["run_name"] == "RUN002_MISSING_KEYS"].iloc[0]["ticket_hyperlink"]
        assert run002_link == '<a href="https://cuhbioinformatics.atlassian.net/browse/KEY-002">RUN002_MISSING_KEYS</a>'

        # Test with a row where ticket_key is None (or NaN after df creation)
        df_no_key = pd.DataFrame({
            'run_name': ['RUN_NO_KEY'],
            'ticket_key': [None]
        })
        df_no_key_linked = general_functions_instance.add_jira_ticket_hyperlink(df_no_key)
        assert df_no_key_linked.iloc[0]["ticket_hyperlink"] == 'RUN_NO_KEY'


    def test_add_run_week(self, general_functions_instance, sample_run_df):
        """Test adding 'run_date' and 'week_start' columns."""
        # sample_run_df's run_names are RUN001, RUN002_MISSING_KEYS
        # Let's assume their dates from names are 230105 and 230106
        # (We need to ensure run_name has a parseable date for this test)
        
        df_input = sample_run_df.copy()
        # Modify run_names to have valid dates for parsing
        df_input.loc[df_input['run_name'] == 'RUN001', 'run_name'] = '230105_RUN001_MOD'
        df_input.loc[df_input['run_name'] == 'RUN002_MISSING_KEYS', 'run_name'] = '230106_RUN002_MOD'
        
        df_with_week = general_functions_instance.add_run_week(df_input)
        
        assert "run_date" in df_with_week.columns
        assert "week_start" in df_with_week.columns
        
        assert pd.api.types.is_datetime64_any_dtype(df_with_week["run_date"])
        
        # Dates: 2023-01-05 (Thursday), 2023-01-06 (Friday)
        # Week starts (assuming Monday): 2023-01-02 for both
        
        run001_date = df_with_week[df_with_week["run_name"] == "230105_RUN001_MOD"].iloc[0]["run_date"]
        run001_week_start = df_with_week[df_with_week["run_name"] == "230105_RUN001_MOD"].iloc[0]["week_start"]
        assert run001_date == pd.Timestamp("2023-01-05")
        assert run001_week_start == "02-01-23" # dd-mm-yy format
        
        run002_date = df_with_week[df_with_week["run_name"] == "230106_RUN002_MOD"].iloc[0]["run_date"]
        run002_week_start = df_with_week[df_with_week["run_name"] == "230106_RUN002_MOD"].iloc[0]["week_start"]
        assert run002_date == pd.Timestamp("2023-01-06")
        assert run002_week_start == "02-01-23"
        
        # Check sorting by date (original order might be RUN001, RUN002)
        # After sorting, it should be 230105_RUN001_MOD then 230106_RUN002_MOD
        assert df_with_week.iloc[0]["run_name"] == "230105_RUN001_MOD"
        assert df_with_week.iloc[1]["run_name"] == "230106_RUN002_MOD"

    def test_create_typo_df(self, general_functions_instance):
        """Test creation of an HTML table for typo information."""
        # Scenario 1: Non-empty list
        typo_list_input = [
            {'assay_type': 'CEN', 'folder_name': 'RUN_FOLDER_CEN', 'project_name_002': 'RUN_PROJ_CEN_TYPO'},
            {'assay_type': 'TSO500', 'jira_ticket_name': 'JIRA_TSO_TYPO', 'run_name': 'RUN_TSO'}
        ]
        html_output = general_functions_instance.create_typo_df(typo_list_input)
        
        assert isinstance(html_output, str)
        assert 'CEN' in html_output
        assert 'RUN_FOLDER_CEN' in html_output
        assert 'RUN_PROJ_CEN_TYPO' in html_output
        assert 'JIRA_TSO_TYPO' in html_output
        assert 'RUN_TSO' in html_output
        assert '<table' in html_output
        assert '<thead>' in html_output # Check for header
        # Check for specific renamed columns
        assert 'Assay type' in html_output 
        assert 'Run name' in html_output # This covers both folder_name and run_name after rename
        assert '002 project name' in html_output
        assert 'Jira ticket name' in html_output


        # Scenario 2: Empty list
        html_output_empty = general_functions_instance.create_typo_df([])
        assert html_output_empty is None

    def test_add_calculation_columns(self, general_functions_instance, mocker):
        """Test the addition of various calculated time difference columns."""
        # Mock current time for calculations involving 'now'
        mock_now = dt.datetime(2023, 2, 10, 12, 0, 0) # February 10, 2023, 12:00:00
        mock_pd_timestamp_now = pd.Timestamp(mock_now)
        mocker.patch('TAT_audit.utils.utils.dt.datetime', MagicMock(now=MagicMock(return_value=mock_now)))
        mocker.patch('TAT_audit.utils.utils.pd.Timestamp', MagicMock(return_value=mock_pd_timestamp_now))


        data = {
            'run_name': ['RUN_COMPLETE', 'RUN_URGENT', 'RUN_ONHOLD', 'RUN_NEGATIVE_TIMES', 'RUN_MISSING_ALL'],
            'upload_time': pd.to_datetime([
                '2023-02-01 10:00:00', # RUN_COMPLETE
                '2023-02-02 10:00:00', # RUN_URGENT
                '2023-02-03 10:00:00', # RUN_ONHOLD
                '2023-02-05 10:00:00', # RUN_NEGATIVE_TIMES
                None                       # RUN_MISSING_ALL
            ]),
            'first_job': pd.to_datetime([
                '2023-02-01 11:00:00', # RUN_COMPLETE (1h after upload)
                '2023-02-02 11:00:00', # RUN_URGENT
                '2023-02-03 11:00:00', # RUN_ONHOLD
                '2023-02-05 09:00:00', # RUN_NEGATIVE_TIMES (first job before upload)
                None
            ]),
            'processing_finished': pd.to_datetime([
                '2023-02-03 11:00:00', # RUN_COMPLETE (2d after first_job)
                '2023-02-04 11:00:00', # RUN_URGENT
                '2023-02-05 11:00:00', # RUN_ONHOLD (processing_finished is last known step)
                '2023-02-05 08:00:00', # RUN_NEGATIVE_TIMES (processing before first_job)
                None
            ]),
            'jira_resolved': pd.to_datetime([
                '2023-02-05 11:00:00', # RUN_COMPLETE (2d after processing_finished)
                None,                      # RUN_URGENT (not resolved)
                None,                      # RUN_ONHOLD (not resolved)
                '2023-02-05 07:00:00', # RUN_NEGATIVE_TIMES (resolved before processing)
                None
            ]),
            'jira_status': [
                'All samples released', 
                'Urgent samples released', 
                'On hold',
                'All samples released', # For RUN_NEGATIVE_TIMES
                None
            ],
            # Fill other necessary columns for ffill in 'last_processing_step'
            # These columns are ['assay_type', 'run_name', 'upload_time', 'first_job', 'processing_finished', ...]
            # The ffill happens on axis 1 from column index 4 ('processing_finished')
            # We need to ensure the structure is similar to the real df for ffill
            # Columns: assay_type, run_name, upload_time, first_job, processing_finished, jira_status, jira_resolved, change_log, ticket_key
            # The ffill is `run_df.ffill(axis=1).iloc[:, 4]` which means it takes the 5th column of the *original* df
            # and then ffills values *horizontally* if there are NaNs later in that row.
            # The `last_processing_step` is then `pd.to_datetime(run_df.ffill(axis=1).iloc[:, 4], errors='coerce')`
            # This means it takes the values from the 'processing_finished' column (original index 4) after it might have been
            # horizontally forward-filled from 'upload_time' or 'first_job' IF 'processing_finished' itself was NaN.
            # This is complex. Let's simplify for the test: ensure 'processing_finished' has values for relevant 'On hold' test.
            # For 'On hold', `last_processing_step` is critical.
            # If 'processing_finished' is present, it's used.
            # If 'processing_finished' is NaN, but 'first_job' is present, 'first_job' is used (due to ffill).
            # If both are NaN, but 'upload_time' is present, 'upload_time' is used.

            # For RUN_ONHOLD, 'processing_finished' is '2023-02-05 11:00:00'. This should be the last_processing_step.
            
            'assay_type': ['CEN'] * 5, # Dummy
            'ticket_key': ['K1'] * 5 # Dummy
        }
        # Ensure correct column order for ffill logic (upload_time, first_job, processing_finished are key)
        # The code ffills from column 4, which is 'processing_finished' in the default column order of create_run_df
        # Let's make sure the test df has a similar structure if ffill is sensitive
        # Columns: assay_type, run_name, upload_time, first_job, processing_finished, ...
        # So iloc[:,4] is indeed 'processing_finished'.
        # The ffill(axis=1) means if df.iloc[row_idx, 4] (processing_finished) is NaN, it takes from df.iloc[row_idx, 3] (first_job) etc.

        df_input = pd.DataFrame(data)
        # Reorder to match expected structure for ffill if necessary, though the iloc[:,4] makes it pick 'processing_finished'
        # if it's the 5th column. The default order from create_run_df is:
        # 'assay_type', 'run_name', 'upload_time', 'first_job', 'processing_finished', ...
        # So iloc[:,4] is indeed 'processing_finished'.
        # The ffill(axis=1) means if df.iloc[row_idx, 4] (processing_finished) is NaN, it takes from df.iloc[row_idx, 3] (first_job) etc.

        df_result = general_functions_instance.add_calculation_columns(df_input.copy()) # Use copy

        # RUN_COMPLETE:
        # upload_to_first_job = 1h = 1/24 days
        # processing_time = 2d
        # processing_end_to_release = 2d
        # upload_to_release = upload_time (01/10:00) to jira_resolved (05/11:00) = 4d + 1h = 4 + 1/24 days
        run_complete = df_result[df_result['run_name'] == 'RUN_COMPLETE'].iloc[0]
        assert pytest.approx(run_complete['upload_to_first_job']) == 1/24
        assert pytest.approx(run_complete['processing_time']) == 2.0
        assert pytest.approx(run_complete['processing_end_to_release']) == 2.0
        assert pytest.approx(run_complete['upload_to_release']) == 4 + 1/24
        assert pd.isna(run_complete['urgents_time'])
        assert pd.isna(run_complete['on_hold_time'])

        # RUN_URGENT: (current time is 2023-02-10 12:00:00)
        # processing_finished = 2023-02-04 11:00:00
        # urgents_time = (2023-02-10 12:00:00) - (2023-02-04 11:00:00) = 6d + 1h
        run_urgent = df_result[df_result['run_name'] == 'RUN_URGENT'].iloc[0]
        assert pd.isna(run_urgent['processing_end_to_release']) # Not 'All samples released'
        assert pd.isna(run_urgent['upload_to_release'])
        assert pytest.approx(run_urgent['urgents_time']) == 6 + 1/24
        assert pd.isna(run_urgent['on_hold_time'])

        # RUN_ONHOLD: (current time is 2023-02-10 12:00:00)
        # last_processing_step should be 'processing_finished' = 2023-02-05 11:00:00
        # on_hold_time = (2023-02-10 12:00:00) - (2023-02-05 11:00:00) = 5d + 1h
        run_onhold = df_result[df_result['run_name'] == 'RUN_ONHOLD'].iloc[0]
        assert run_onhold['last_processing_step'] == pd.Timestamp('2023-02-05 11:00:00')
        assert pd.isna(run_onhold['urgents_time'])
        assert pytest.approx(run_onhold['on_hold_time']) == 5 + 1/24
        
        # RUN_NEGATIVE_TIMES:
        # upload_to_first_job = -1h
        # processing_time = -1h
        # processing_end_to_release = -1h
        # upload_to_release should be NaN because individual steps are negative.
        run_negative = df_result[df_result['run_name'] == 'RUN_NEGATIVE_TIMES'].iloc[0]
        assert pytest.approx(run_negative['upload_to_first_job']) == -1/24
        assert pytest.approx(run_negative['processing_time']) == -1/24
        assert pytest.approx(run_negative['processing_end_to_release']) == -1/24
        assert pd.isna(run_negative['upload_to_release']) # Due to conditions in .where()

        # RUN_MISSING_ALL: all calculated time columns should be NaN
        run_missing = df_result[df_result['run_name'] == 'RUN_MISSING_ALL'].iloc[0]
        time_cols = ['upload_to_first_job', 'processing_time', 'processing_end_to_release', 
                     'upload_to_release', 'urgents_time', 'on_hold_time']
        for col in time_cols:
            assert pd.isna(run_missing[col])
        assert pd.isna(run_missing['last_processing_step'])


    # More tests here
