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
        """Test create_run_df with an empty input dictionary - expecting SystemExit."""
        mock_sys_exit = mocker.patch('TAT_audit.utils.utils.sys.exit')

        with pytest.raises(SystemExit) as excinfo:
            general_functions_instance.create_run_df({})

        # Optionally, assert the exit code if it's important
        # assert excinfo.value.code == 1
        mock_sys_exit.assert_called_once_with(1) # Check it was called with exit code 1

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
        # mock_pd_timestamp_now = pd.Timestamp(mock_now) # Not strictly needed if pd.Timestamp mock is removed
        mocker.patch('TAT_audit.utils.utils.dt.datetime', MagicMock(now=MagicMock(return_value=mock_now)))
        # mocker.patch('TAT_audit.utils.utils.pd.Timestamp', MagicMock(return_value=mock_pd_timestamp_now)) # This was problematic


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


    def test_extract_assay_df(self, general_functions_instance, sample_run_df):
        """Test extracting a DataFrame for a specific assay type."""
        # sample_run_df has RUN001 (CEN) and RUN002_MISSING_KEYS (TSO500)
        # Ensure run_names are updated to something that won't break date parsing in add_run_week if it was called
        # For this test, we only care about 'assay_type' column.
        df_input = sample_run_df.copy()
        df_input.loc[df_input['run_name'] == 'RUN001', 'assay_type'] = 'CEN'
        df_input.loc[df_input['run_name'] == 'RUN002_MISSING_KEYS', 'assay_type'] = 'TSO500'


        cen_df = general_functions_instance.extract_assay_df(df_input, "CEN")
        assert len(cen_df) == 1
        assert cen_df.iloc[0]["assay_type"] == "CEN"
        assert cen_df.iloc[0]["run_name"] == "RUN001" # or modified name if sample_run_df fixture is changed

        tso_df = general_functions_instance.extract_assay_df(df_input, "TSO500")
        assert len(tso_df) == 1
        assert tso_df.iloc[0]["assay_type"] == "TSO500"
        assert tso_df.iloc[0]["run_name"] == "RUN002_MISSING_KEYS" # or modified name

        mye_df = general_functions_instance.extract_assay_df(df_input, "MYE")
        assert len(mye_df) == 0

    def test_make_stats_table(self, general_functions_instance):
        """Test generation of the HTML stats table and compliance metrics."""
        # tat_standard is 7 days for the fixture instance
        data_compliant = {
            'upload_to_release': [5.0, 6.5, 7.0], # All compliant or at boundary
            'upload_to_first_job': [1,1,1], # All positive
            'processing_time': [1,1,1],       # All positive
            'processing_end_to_release': [1,1,1], # All positive
            'urgents_time': [None, None, None] # Not urgent
        }
        df_compliant = pd.DataFrame(data_compliant)
        stats_html, fraction, percentage = general_functions_instance.make_stats_table(df_compliant)
        assert "<td>(3/3)  100.0%</td>" in stats_html # Adjusted for potential double space
        assert fraction == "(3/3) "
        assert percentage == 100.0

        data_mixed = {
            'upload_to_release': [5.0, 8.0, 7.5, None, 6.0], # 2 compliant (5.0, 6.0)
            'upload_to_first_job': [1, 1, 1, 1, -1], # Last one has negative step, makes upload_to_release NaN for it effectively
            'processing_time': [1, 1, 1, 1, 1],
            'processing_end_to_release': [1, 1, 1, 1, 1],
            'urgents_time': [None, None, None, 1.0, None] # One urgent, not counted in compliance normally
        }
        # For data_mixed, upload_to_release for the last row will be NaN due to negative step.
        # Relevant runs for compliance: those with positive steps and notna upload_to_release.
        # Run 1: 5.0 (compliant)
        # Run 2: 8.0 (not compliant)
        # Run 3: 7.5 (not compliant)
        # Run 4: None (upload_to_release is None, but urgents_time is present) -> relevant_run_count includes this
        # Run 5: upload_to_release will be NaN due to negative step.
        # So, relevant_run_count = 4 (first four rows where steps are positive and either UTR or urgent time is notna)
        # Compliant runs = 1 (only the first row: 5.0)
        df_mixed = pd.DataFrame(data_mixed)
        stats_html_mixed, fraction_mixed, percentage_mixed = general_functions_instance.make_stats_table(df_mixed)
        assert "<td>(1/4)  25.0%</td>" in stats_html_mixed # Adjusted for potential double space
        assert fraction_mixed == "(1/4) "
        assert percentage_mixed == 25.0
        assert "Mean overall TAT" in stats_html_mixed
        assert "Median overall TAT" in stats_html_mixed

        # Test with df where all UTR are NaN but urgents_time is present
        data_all_urgent_no_utr = {
            'upload_to_release': [None, None],
            'upload_to_first_job': [1,1],
            'processing_time': [1,1],
            'processing_end_to_release': [1,1], # These would normally be NaN if UTR is NaN due to status
            'urgents_time': [1.0, 2.0]
        }
        df_all_urgent = pd.DataFrame(data_all_urgent_no_utr)
        stats_html_urgent, fraction_urgent, percentage_urgent = general_functions_instance.make_stats_table(df_all_urgent)
        assert "<td>(0/2)  0.0%</td>" in stats_html_urgent # No UTR values to be compliant with, added double space
        assert fraction_urgent == "(0/2) "
        assert percentage_urgent == 0.0


        # Test with an empty DataFrame
        empty_df = pd.DataFrame(columns=['upload_to_release', 'upload_to_first_job', 'processing_time', 'processing_end_to_release', 'urgents_time'])
        stats_html_empty, fraction_empty, percentage_empty = general_functions_instance.make_stats_table(empty_df)
        assert stats_html_empty == pd.DataFrame({}).to_html(index=False, float_format='{:.2f}'.format, classes='table table-striped"', justify='left')
        assert fraction_empty is None
        assert percentage_empty is None

        # Test with DataFrame where relevant_run_count is 0
        df_zero_relevant = pd.DataFrame({
            'upload_to_release': [None, None],
            'upload_to_first_job': [-1, -1], # Negative steps
            'processing_time': [1,1],
            'processing_end_to_release': [1,1],
            'urgents_time': [None,None]
        })
        stats_html_zero, fraction_zero, percentage_zero = general_functions_instance.make_stats_table(df_zero_relevant)
        assert stats_html_zero == pd.DataFrame({}).to_html(index=False, float_format='{:.2f}'.format, classes='table table-striped"', justify='left')
        assert fraction_zero == "(0/0)" # This is the specific string for this case
        assert percentage_zero == 0.0


    def test_find_runs_for_manual_review(self, general_functions_instance):
        """Test identifying runs that need manual review based on data anomalies."""
        # import pandas as pd # Ensure pandas is imported if not already at top of file for this snippet
        # data_for_debug = {
        #    'run_name': ['RUN_JOB_BEFORE_LOG', 'RUN_NO_LOG'],
        #    'upload_time': [pd.Timestamp("2023-01-01"), None],
        #    'upload_to_first_job': [-1, 1],
        #    'jira_status': ['All samples released', 'All samples released']
        # }
        # df_debug = pd.DataFrame(data_for_debug)
        # rjbl_upload_time = df_debug[df_debug['run_name'] == 'RUN_JOB_BEFORE_LOG']['upload_time'].iloc[0]
        # print(f"[DEBUG TEST] RUN_JOB_BEFORE_LOG upload_time: {rjbl_upload_time}, isna: {pd.isna(rjbl_upload_time)}")
        # rnl_upload_time = df_debug[df_debug['run_name'] == 'RUN_NO_LOG']['upload_time'].iloc[0] # This will be NaT
        # print(f"[DEBUG TEST] RUN_NO_LOG upload_time: {rnl_upload_time}, isna: {pd.isna(rnl_upload_time)}")
        # general_functions_instance.cancelled_statuses = ["Cancelled", "Data not received"]
        # general_functions_instance.open_statuses = ["Open", "On Hold"]
        data = {
            'run_name': ['RUN_OK', 'RUN_NO_JIRA', 'RUN_JOB_BEFORE_LOG', 'RUN_NO_LOG', 'RUN_NO_FIRST_JOB', 'RUN_NO_FINAL_JOB', 'RUN_CANCELLED_OK', 'RUN_OPEN_OK'],
            'jira_status': [
                'All samples released', None, 'All samples released', 'All samples released',
                'All samples released', 'All samples released', 'Cancelled', 'Open'
            ],
            'upload_time': [
                pd.Timestamp("2023-01-01"), # RUN_OK
                pd.Timestamp("2023-01-01"), # RUN_NO_JIRA
                pd.Timestamp("2023-01-03"), # RUN_JOB_BEFORE_LOG <--- Was None, now a Timestamp
                None,                       # RUN_NO_LOG <--- Was a Timestamp, now None
                pd.Timestamp("2023-01-01"), # RUN_NO_FIRST_JOB
                pd.Timestamp("2023-01-01"), # RUN_NO_FINAL_JOB
                pd.Timestamp("2023-01-01"), # RUN_CANCELLED_OK
                pd.Timestamp("2023-01-01")  # RUN_OPEN_OK
            ],
            'first_job': [
                pd.Timestamp("2023-01-01"), # RUN_OK
                pd.Timestamp("2023-01-01"), # RUN_NO_JIRA
                pd.Timestamp("2023-01-03"), # RUN_JOB_BEFORE_LOG (valid first_job as upload_to_first_job is -1)
                None,                       # RUN_NO_LOG
                None,                       # RUN_NO_FIRST_JOB <--- This is now None
                pd.Timestamp("2023-01-01"), # RUN_NO_FINAL_JOB
                pd.Timestamp("2023-01-01"), # RUN_CANCELLED_OK
                pd.Timestamp("2023-01-01")  # RUN_OPEN_OK
            ],
            'processing_finished': [pd.Timestamp("2023-01-01")]*5 + [None] + [pd.Timestamp("2023-01-01")]*2, # RUN_NO_FINAL_JOB has None
            'upload_to_first_job': [1, 1, -1, 1, 1, 1, 1, 1] # RUN_JOB_BEFORE_LOG is < 0
        }
        df_input = pd.DataFrame(data)
        df_input['upload_time'] = pd.to_datetime(df_input['upload_time'])
        df_input['first_job'] = pd.to_datetime(df_input['first_job'])
        df_input['processing_finished'] = pd.to_datetime(df_input['processing_finished'])

        # Debug print inside the test:
        # rjbl_upload_time_in_test = df_input[df_input['run_name'] == 'RUN_JOB_BEFORE_LOG']['upload_time'].iloc[0]
        # print(f"IN-TEST DEBUG: RUN_JOB_BEFORE_LOG upload_time: {rjbl_upload_time_in_test}, isna: {pd.isna(rjbl_upload_time_in_test)}, dtype: {df_input['upload_time'].dtype}")

        review_dict = general_functions_instance.find_runs_for_manual_review(df_input)

        assert review_dict['no_jira_tix'] == ['RUN_NO_JIRA']
        assert review_dict['first_job_before_log'] == ['RUN_JOB_BEFORE_LOG']
        # For 'no_log_file', 'no_first_job_found', 'no_final_job_found', it should not include cancelled/open runs
        assert review_dict['no_log_file'] == ['RUN_NO_LOG']
        assert sorted(review_dict['no_first_job_found']) == sorted(['RUN_NO_LOG', 'RUN_NO_FIRST_JOB'])
        assert review_dict['no_final_job_found'] == ['RUN_NO_FINAL_JOB']

        # Test with no issues
        df_all_ok = pd.DataFrame({
            'run_name': ['RUN_PERFECT'], 'jira_status': ['All samples released'],
            'upload_time': [pd.Timestamp("2023-01-01")], 'first_job': [pd.Timestamp("2023-01-01")],
            'processing_finished': [pd.Timestamp("2023-01-01")], 'upload_to_first_job': [1]
        })
        review_dict_ok = general_functions_instance.find_runs_for_manual_review(df_all_ok)
        assert review_dict_ok == {} # Empty dict if no issues

    @patch.object(GeneralFunctions, 'extract_assay_df')
    @patch.object(GeneralFunctions, 'make_stats_table')
    @patch.object(GeneralFunctions, 'find_runs_for_manual_review')
    def test_create_assay_objects(self, mock_find_review, mock_make_stats, mock_extract_df, general_functions_instance):
        """Test the creation of assay-specific objects (df, stats, issues, etc.)."""
        mock_all_assays_df = MagicMock(spec=pd.DataFrame)
        assay_type_input = "CEN"

        # Mock return values from the helper methods
        mock_extracted_assay_df = MagicMock(spec=pd.DataFrame)
        mock_extracted_assay_df.shape = [5, 10] # Simulate 5 runs
        mock_extract_df.return_value = mock_extracted_assay_df

        mock_stats_table_html = "<table_stats/>"
        mock_compliance_fraction = "(4/5) "
        mock_compliance_percentage = 80.0
        mock_make_stats.return_value = (mock_stats_table_html, mock_compliance_fraction, mock_compliance_percentage)

        mock_issues_dict = {"no_log_file": ["RUN_X"]}
        mock_find_review.return_value = mock_issues_dict

        (res_assay_df, res_stats, res_issues, res_run_count,
         res_fraction, res_percentage) = general_functions_instance.create_assay_objects(mock_all_assays_df, assay_type_input)

        mock_extract_df.assert_called_once_with(mock_all_assays_df, assay_type_input)
        assert res_assay_df == mock_extracted_assay_df
        assert res_run_count == 5 # from mock_extracted_assay_df.shape[0]

        mock_make_stats.assert_called_once_with(mock_extracted_assay_df)
        assert res_stats == mock_stats_table_html
        assert res_fraction == mock_compliance_fraction
        assert res_percentage == mock_compliance_percentage

        mock_find_review.assert_called_once_with(mock_extracted_assay_df)
        assert res_issues == mock_issues_dict

    def test_add_in_cancelled_runs(self, general_functions_instance):
        """Test adding cancelled runs (from Jira only) to the main DataFrame and sorting."""
        initial_df_data = {
            'run_name': ['230105_RUN_CEN_002', '230103_RUN_MYE_002'], # Dates: 05 Jan, 03 Jan
            'assay_type': ['CEN', 'MYE'],
            'upload_time': [pd.Timestamp("2023-01-05")]*2, # Dummy
            # Add other columns expected by the function to avoid issues if they are accessed
            'first_job': [None]*2, 'processing_finished': [None]*2, 'jira_status': [None]*2,
            'jira_resolved': [None]*2, 'change_log': [None]*2, 'ticket_key': [None]*2,
            'upload_to_first_job': [None]*2, 'processing_time': [None]*2,
            'processing_end_to_release': [None]*2, 'upload_to_release': [None]*2,
            'urgents_time': [None]*2, 'on_hold_time': [None]*2, 'last_processing_step': [None]*2,
            'ticket_hyperlink': [None]*2, 'run_date': [None]*2, 'week_start': [None]*2
        }
        all_assays_df_input = pd.DataFrame(initial_df_data)

        cancelled_runs_input = [
            {'run_name': '230104_RUN_CEN_JIRA_CANCELLED', 'assay_type': 'CEN', 'jira_status': 'Cancelled'}, # 04 Jan
            {'run_name': '230102_RUN_TSO_JIRA_CANCELLED', 'assay_type': 'TSO500', 'jira_status': 'Data not received'} # 02 Jan
        ]

        result_df = general_functions_instance.add_in_cancelled_runs(all_assays_df_input.copy(), cancelled_runs_input)

        assert len(result_df) == 4 # 2 initial + 2 cancelled
        assert '230104_RUN_CEN_JIRA_CANCELLED' in result_df['run_name'].values
        assert '230102_RUN_TSO_JIRA_CANCELLED' in result_df['run_name'].values

        # Check final sort order:
        # 1. CEN (custom_dict order 0)
        #    - 230104_RUN_CEN_JIRA_CANCELLED (date 04)
        #    - 230105_RUN_CEN_002 (date 05)
        # 2. MYE (custom_dict order 1)
        #    - 230103_RUN_MYE_002 (date 03)
        # 3. TSO500 (custom_dict order 2)
        #    - 230102_RUN_TSO_JIRA_CANCELLED (date 02)

        # Expected order of run_names after sorting:
        expected_run_name_order = [
            '230104_RUN_CEN_JIRA_CANCELLED', # CEN, 04 Jan
            '230105_RUN_CEN_002',          # CEN, 05 Jan
            '230103_RUN_MYE_002',          # MYE, 03 Jan
            '230102_RUN_TSO_JIRA_CANCELLED'  # TSO500, 02 Jan
        ]
        assert list(result_df['run_name']) == expected_run_name_order

        # Check that 'date' column (used for sorting) is dropped
        assert 'date' not in result_df.columns

        # Test with duplicate run name (one from 002, one from Jira cancelled)
        # The one from Jira (last one after append) should be kept if drop_duplicates(subset=['run_name'], keep='last')
        df_with_duplicate = pd.DataFrame({
            'run_name': ['230110_DUPLICATE_RUN'], 'assay_type': ['CEN'], 'upload_time': [pd.Timestamp("2023-01-10")]
        })
        cancelled_duplicate = [{'run_name': '230110_DUPLICATE_RUN', 'assay_type': 'CEN', 'jira_status': 'Cancelled', 'custom_field': 'from_jira'}]

        result_dup_df = general_functions_instance.add_in_cancelled_runs(df_with_duplicate.copy(), cancelled_duplicate)
        assert len(result_dup_df) == 1
        assert result_dup_df.iloc[0].get('custom_field') == 'from_jira' # Check if the Jira version was kept


    @patch('pandas.DataFrame.to_csv')
    def test_write_to_csv(self, mock_to_csv, general_functions_instance, sample_run_df):
        """Test writing the final DataFrame to a CSV file."""
        # general_functions_instance has audit_start="2023-01-01", audit_end="2023-01-31"
        df_input = sample_run_df.copy()
        # Add columns that should be dropped to test that part
        df_input['change_log'] = [None] * len(df_input)
        df_input['ticket_hyperlink'] = [None] * len(df_input)
        df_input['run_date'] = [None] * len(df_input)

        general_functions_instance.write_to_csv(df_input)

        expected_filename = f'audit_info_{general_functions_instance.audit_start}_{general_functions_instance.audit_end}.csv'

        # Check that to_csv was called on the DataFrame *after* dropping columns
        # The DataFrame passed to to_csv should not have the dropped columns.
        # We can grab the DataFrame instance that to_csv was called with.
        assert mock_to_csv.call_count == 1
        call_args = mock_to_csv.call_args
        df_passed_to_csv = call_args.args[0] # The DataFrame instance is the first positional arg to to_csv (or use call_args.instance if to_csv is a method of a mock)
                                            # Here, it's a method of a real DataFrame, so it's the first arg.

        # It's tricky to get the df instance directly if to_csv is called on `all_assays_df` which is modified in place.
        # Let's verify by checking the arguments passed to `to_csv`.
        # The first argument to to_csv will be the filename.

        mock_to_csv.assert_called_once_with(
            expected_filename,
            float_format='%.3f',
            index=False
        )

        # To check if columns were dropped, we'd ideally inspect the df instance.
        # Since df_input is modified in place by drop, we can check its columns *after* the call.
        assert 'change_log' not in df_input.columns
        assert 'ticket_hyperlink' not in df_input.columns
        assert 'run_date' not in df_input.columns

    # End of TestGeneralFunctions class
