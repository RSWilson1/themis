import datetime as dt
import pandas as pd
import pytest
import sys

from TAT_audit.utils import utils as ut


@pytest.fixture
def gen_funcs():
    """
    General functions for use in tests
    """
    gen_funcs = ut.GeneralFunctions(
        tat_standard=3,
        cancelled_statuses=["Cancelled", "Cancelling"],
        open_statuses=["Open", "Reopened"],
        audit_start="010122",
        audit_end="010123"
    )
    return gen_funcs


@pytest.fixture
def test_df_for_add_calc_cols(gen_funcs):
    """
    Test df for adding calculation columns
    """
    test_df = pd.DataFrame({
        'assay_type': ['CEN'],
        'run_name': ['220101_TEST_RUN'],
        'upload_time': ['2022-01-01 10:00:00'],
        'first_job': ['2022-01-01 11:00:00'],
        'processing_finished': ['2022-01-02 12:00:00'],
        'jira_status': ['All samples released'],
        'jira_resolved': ['2022-01-03 13:00:00'],
        'change_log': ['some log'],
        'ticket_key': ['JIRA-123']
    })

    # Convert relevant columns to datetime
    for col in ['upload_time', 'first_job', 'processing_finished', 'jira_resolved']:
        test_df[col] = pd.to_datetime(test_df[col])

    return test_df


@pytest.fixture
def test_df_for_stats(gen_funcs):
    """
    Test df for making stats table
    """
    df_dict = {
        'assay_type': ['CEN', 'CEN', 'CEN', 'CEN'],
        'run_name': [
            '220101_RUN1', '220102_RUN2', '220103_RUN3', '220104_RUN4'
        ],
        'upload_time': [
            '2022-01-01 10:00:00', '2022-01-02 10:00:00',
            '2022-01-03 10:00:00', '2022-01-04 10:00:00'
        ],
        'first_job': [
            '2022-01-01 11:00:00', '2022-01-02 11:00:00',
            '2022-01-03 11:00:00', '2022-01-04 11:00:00'
        ],
        'processing_finished': [
            '2022-01-02 12:00:00', '2022-01-03 12:00:00',
            '2022-01-04 12:00:00', '2022-01-05 12:00:00'
        ],
        'jira_status': [
            'All samples released', 'All samples released',
            'All samples released', 'Urgent samples released'
        ],
        'jira_resolved': [
            '2022-01-03 13:00:00', '2022-01-04 13:00:00',
            '2022-01-05 13:00:00', pd.NaT  # RUN4 not fully resolved
        ],
        'upload_to_release': [2.125, 2.125, 2.125, pd.NA], # (resolved - upload) in days
        'upload_to_first_job': [0.041667, 0.041667, 0.041667, 0.041667],
        'processing_time': [1.041667, 1.041667, 1.041667, 1.041667],
        'processing_end_to_release': [1.041667, 1.041667, 1.041667, pd.NA],
        'urgents_time': [pd.NA, pd.NA, pd.NA, pd.NA] # Placeholder, will be calculated dynamically if needed
    }
    df = pd.DataFrame(df_dict)
    for col in ['upload_time', 'first_job', 'processing_finished', 'jira_resolved']:
        df[col] = pd.to_datetime(df[col])

    # Calculate urgents_time for the 'Urgent samples released' case based on a fixed 'now'
    # For testing consistency, let's define 'now' as 2022-01-06 12:00:00 for RUN4
    fixed_now = pd.Timestamp('2022-01-06 12:00:00')
    if df.loc[3, 'jira_status'] == 'Urgent samples released':
        df.loc[3, 'urgents_time'] = (fixed_now - df.loc[3, 'processing_finished']) / pd.Timedelta(days=1)
    return df


@pytest.fixture
def test_df_for_manual_review(gen_funcs):
    """
    Test df for finding runs for manual review
    """
    # Corrected data for upload_time and first_job
    df_dict = {
        'assay_type': ['CEN'] * 6,
        'run_name': [
            'RUN_NO_JIRA', 'RUN_JOB_BEFORE_LOG', 'RUN_NO_LOG',
            'RUN_NO_FIRST_JOB', 'RUN_NO_FINAL_JOB', 'RUN_OK'
        ],
        'upload_time': [
            '2022-01-01 10:00:00', '2022-01-02 10:00:00', # RUN_JOB_BEFORE_LOG
            pd.NaT, # RUN_NO_LOG
            '2022-01-04 10:00:00', '2022-01-05 10:00:00', '2022-01-06 10:00:00'
        ],
        'first_job': [
            '2022-01-01 11:00:00', '2022-01-02 09:00:00', # RUN_JOB_BEFORE_LOG (job before log)
            '2022-01-03 11:00:00', # RUN_NO_LOG (log is NaT, job is present)
            pd.NaT, # RUN_NO_FIRST_JOB
            '2022-01-05 11:00:00', '2022-01-06 11:00:00'
        ],
        'processing_finished': [
            '2022-01-02 12:00:00', '2022-01-03 12:00:00',
            '2022-01-04 12:00:00', '2022-01-05 12:00:00',
            pd.NaT, # RUN_NO_FINAL_JOB
            '2022-01-07 12:00:00'
        ],
        'jira_status': [
            pd.NaT, # RUN_NO_JIRA
            'All samples released', 'All samples released',
            'All samples released', 'All samples released', 'All samples released'
        ],
        'jira_resolved': [pd.NaT] * 6, # Not relevant for this test focus
        'upload_to_first_job': [
            0.041667, -0.041667, # RUN_JOB_BEFORE_LOG (negative TAT)
            pd.NA, # RUN_NO_LOG (cannot calculate)
            pd.NA, # RUN_NO_FIRST_JOB (cannot calculate)
            0.041667, 0.041667
        ],
        'ticket_key': [
            pd.NaT, 'JIRA-2', 'JIRA-3', 'JIRA-4', 'JIRA-5', 'JIRA-6'
        ]
    }
    df = pd.DataFrame(df_dict)
    for col in ['upload_time', 'first_job', 'processing_finished', 'jira_resolved']:
        df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


@pytest.fixture
def all_assays_df_for_cancelled_runs():
    data = {
        'run_name': ['220101_RUN1_ASSAY1', '220102_RUN2_ASSAY1'],
        'assay_type': ['ASSAY1', 'ASSAY1'],
        'upload_time': [pd.Timestamp('2022-01-01 10:00:00'), pd.Timestamp('2022-01-02 10:00:00')],
        'first_job': [pd.Timestamp('2022-01-01 11:00:00'), pd.Timestamp('2022-01-02 11:00:00')],
        'processing_finished': [pd.Timestamp('2022-01-01 12:00:00'), pd.Timestamp('2022-01-02 12:00:00')],
        'jira_status': ['All samples released', 'All samples released'],
        'jira_resolved': [pd.Timestamp('2022-01-01 13:00:00'), pd.Timestamp('2022-01-02 13:00:00')],
        'change_log': ['log1', 'log2'],
        'ticket_key': ['JIRA-1', 'JIRA-2']
    }
    return pd.DataFrame(data)


@pytest.fixture
def cancelled_runs_list():
    return [
        {
            'run_name': '220103_RUN3_CANCELLED', 'assay_type': 'ASSAY1',
            'jira_status': 'Cancelled', 'ticket_key': 'JIRA-3',
            'upload_time': pd.NaT, 'first_job': pd.NaT, 'processing_finished': pd.NaT, 'jira_resolved': pd.NaT, 'change_log': None
        },
        {
            'run_name': '220101_RUN1_ASSAY1', 'assay_type': 'ASSAY1', # Duplicate, should be handled
            'jira_status': 'Cancelled', 'ticket_key': 'JIRA-4',
            'upload_time': pd.NaT, 'first_job': pd.NaT, 'processing_finished': pd.NaT, 'jira_resolved': pd.NaT, 'change_log': None
        }
    ]


class TestGeneralFunctions:
    """
    Test general functions class
    """
    def test_add_in_empty_keys(self, gen_funcs):
        """
        Test empty keys are added to dict
        """
        test_dict = {
            'test_run1': {'assay_type': 'CEN'},
            'test_run2': {'assay_type': 'MYE', 'upload_time': 'val'}
        }
        filled_dict = gen_funcs.add_in_empty_keys(test_dict)
        expected_keys = [
            'upload_time', 'first_job', 'processing_finished',
            'jira_status', 'jira_resolved', 'change_log', 'ticket_key'
        ]
        # Check all keys are now in there for first run
        for key in expected_keys:
            assert key in filled_dict['test_run1']

        # Check second run which had one key already keeps that key
        assert filled_dict['test_run2']['upload_time'] == 'val'
        # And that others were added
        for key in expected_keys[1:]:
            assert key in filled_dict['test_run2']

    def test_create_run_df_empty_dict(self, gen_funcs):
        """
        Test that an empty DataFrame with expected columns is returned
        when an empty dict is passed and that SystemExit is not called.
        """
        run_dict = {}
        expected_cols = [
            'assay_type', 'run_name', 'upload_time', 'first_job',
            'processing_finished', 'jira_status', 'jira_resolved',
            'change_log', 'ticket_key'
        ]
        df = gen_funcs.create_run_df(run_dict)
        assert isinstance(df, pd.DataFrame), "Should return a DataFrame"
        assert df.empty, "DataFrame should be empty"
        assert list(df.columns) == expected_cols, "DataFrame should have expected columns"
        # Check dtypes for datetime columns if the logic enforces it for empty df
        for col in ['upload_time', 'first_job', 'processing_finished', 'jira_resolved']:
            assert pd.api.types.is_datetime64_any_dtype(df[col]) or df[col].isnull().all()


    def test_create_run_df_with_data(self, gen_funcs):
        """
        Test df is created from dict correctly
        """
        test_dict = {
            '220101_RUN1': {
                'assay_type': 'CEN', 'upload_time': '2022-01-01 10:00:00',
                'first_job': '2022-01-01 11:00:00',
                'processing_finished': '2022-01-01 12:00:00',
                'jira_status': 'All samples released',
                'jira_resolved': '2022-01-01 13:00:00',
                'change_log': 'log1', 'ticket_key': 'key1'
            }
        }
        df = gen_funcs.create_run_df(test_dict)
        assert not df.empty
        assert df.shape[0] == 1
        assert df.iloc[0]['run_name'] == '220101_RUN1'
        assert df.iloc[0]['assay_type'] == 'CEN'
        assert pd.Timestamp(df.iloc[0]['upload_time']) == pd.Timestamp('2022-01-01 10:00:00')

    def test_generate_hyperlink(self, gen_funcs):
        """
        Test hyperlink is generated correctly
        """
        row = pd.Series({
            'ticket_key': 'JIRA-123', 'run_name': '220101_TEST_RUN'
        })
        link = gen_funcs.generate_hyperlink(row)
        expected_link = '<a href="https://cuhbioinformatics.atlassian.net/browse/JIRA-123">220101_TEST_RUN</a>'
        assert link == expected_link

    def test_add_jira_ticket_hyperlink(self, gen_funcs):
        """
        Test hyperlink col is added correctly
        """
        test_df = pd.DataFrame({
            'run_name': ['220101_RUN1', '220102_RUN2'],
            'ticket_key': ['JIRA-1', pd.NA]
        })
        df_with_link = gen_funcs.add_jira_ticket_hyperlink(test_df.copy()) # Use copy to avoid SettingWithCopyWarning
        assert 'ticket_hyperlink' in df_with_link.columns
        assert 'href="https://cuhbioinformatics.atlassian.net/browse/JIRA-1"' in df_with_link.iloc[0]['ticket_hyperlink']
        assert df_with_link.iloc[1]['ticket_hyperlink'] == '220102_RUN2' # No key, should be run_name

    def test_add_run_week(self, gen_funcs):
        """
        Test week is added correctly
        """
        test_df = pd.DataFrame({
            'run_name': ['220103_RUN1'] # Monday 3rd Jan 2022
        })
        df_with_week = gen_funcs.add_run_week(test_df)
        assert 'run_date' in df_with_week.columns
        assert 'week_start' in df_with_week.columns
        assert pd.Timestamp(df_with_week.iloc[0]['run_date']) == pd.Timestamp('2022-01-03')
        assert df_with_week.iloc[0]['week_start'] == '03-01-22' # Week starting Monday 3rd Jan

    def test_create_typo_df(self, gen_funcs):
        """
        Test typo df created correctly
        """
        typo_list_empty = []
        typo_list_filled = [{
            'jira_ticket_name': 'name1', 'run_name': 'name2',
            'assay_type': 'CEN'
        }]
        assert gen_funcs.create_typo_df(typo_list_empty) is None
        html_table = gen_funcs.create_typo_df(typo_list_filled)
        assert html_table is not None
        assert '<td>name1</td>' in html_table
        assert '<td>name2</td>' in html_table
        assert '<td>CEN</td>' in html_table

    def test_add_calculation_columns(self, gen_funcs, test_df_for_add_calc_cols):
        """
        Test calculation columns are added correctly
        """
        df = gen_funcs.add_calculation_columns(test_df_for_add_calc_cols)
        # Expected: (11:00:00 - 10:00:00) = 1 hour = 1/24 days
        assert abs(df.iloc[0]['upload_to_first_job'] - (1/24)) < 0.0001
        # Expected: (Jan 02 12:00:00 - Jan 01 11:00:00) = 25 hours = 25/24 days
        assert abs(df.iloc[0]['processing_time'] - (25/24)) < 0.0001
        # Expected: (Jan 03 13:00:00 - Jan 02 12:00:00) = 25 hours = 25/24 days
        assert abs(df.iloc[0]['processing_end_to_release'] - (25/24)) < 0.0001
        # Expected: (Jan 03 13:00:00 - Jan 01 10:00:00) = 51 hours = 51/24 days
        assert abs(df.iloc[0]['upload_to_release'] - (51/24)) < 0.0001
        assert pd.isna(df.iloc[0]['urgents_time']) # Status is not 'Urgent samples released'
        assert pd.isna(df.iloc[0]['on_hold_time']) # Status is not 'On hold'

    def test_extract_assay_df(self, gen_funcs):
        """
        Test assay df extracted correctly
        """
        test_df = pd.DataFrame({
            'assay_type': ['CEN', 'MYE', 'CEN'],
            'data': [1,2,3]
        })
        cen_df = gen_funcs.extract_assay_df(test_df, 'CEN')
        mye_df = gen_funcs.extract_assay_df(test_df, 'MYE')
        assert cen_df.shape[0] == 2
        assert mye_df.shape[0] == 1
        assert cen_df.iloc[0]['data'] == 1
        assert cen_df.iloc[1]['data'] == 3 # Original index is reset
        assert mye_df.iloc[0]['data'] == 2

    def test_make_stats_table_empty_df(self, gen_funcs):
        """
        Test that an empty df and None values are returned for an empty df
        """
        empty_assay_df = pd.DataFrame(columns=[
            'upload_to_release', 'upload_to_first_job', 'processing_time',
            'processing_end_to_release', 'urgents_time'
        ]) # Must have these columns for the function to run
        stats_table, compliance_fraction, compliance_percentage = gen_funcs.make_stats_table(empty_assay_df)
        assert stats_table == pd.DataFrame({}).to_html(
            index=False, float_format='{:.2f}'.format,
            classes='table table-striped"', justify='left'
        ) # Empty table
        assert compliance_fraction is None
        assert compliance_percentage is None

    def test_make_stats_table_with_data(self, gen_funcs, test_df_for_stats):
        """
        Test stats table created correctly
        """
        stats_table, compliance_fraction, compliance_percentage = gen_funcs.make_stats_table(test_df_for_stats)
        assert '<td>Mean overall TAT</td>' in stats_table
        assert '<td>2.12</td>' in stats_table # Mean of [2.125, 2.125, 2.125]
        assert '<td>Median overall TAT</td>' in stats_table # Median
        assert '<td>Mean upload to processing start</td>' in stats_table
        assert '<td>0.04</td>' in stats_table # Mean of [0.041667]*3
        assert '<td>Compliance with audit standards</td>' in stats_table
        # All 3 relevant runs are <= 3 days TAT
        assert '<td>(3/3)100.0%</td>' in stats_table.replace(" ", "") # Ensure no spaces in assertion string
        assert compliance_fraction == "(3/3) "
        assert compliance_percentage == 100.0

    def test_make_stats_table_no_relevant_runs(self, gen_funcs):
        """
        Test stats table when no runs meet criteria for TAT calculation.
        """
        df_dict = {
            'assay_type': ['CEN'], 'run_name': ['220101_RUN1'],
            'upload_time': [pd.NaT], 'first_job': [pd.NaT],
            'processing_finished': [pd.NaT], 'jira_status': ['Open'],
            'jira_resolved': [pd.NaT], 'upload_to_release': [pd.NA],
            'upload_to_first_job': [pd.NA], 'processing_time': [pd.NA],
            'processing_end_to_release': [pd.NA], 'urgents_time': [pd.NA]
        }
        no_relevant_df = pd.DataFrame(df_dict)
        for col in ['upload_time', 'first_job', 'processing_finished', 'jira_resolved']:
             no_relevant_df[col] = pd.to_datetime(no_relevant_df[col])

        stats_table, compliance_fraction, compliance_percentage = gen_funcs.make_stats_table(no_relevant_df)
        assert compliance_percentage == 0.0
        assert compliance_fraction == "(0/0)"
        # Check for an empty stats table (or specific message if applicable)
        assert stats_table == pd.DataFrame({}).to_html(
            index=False, float_format='{:.2f}'.format,
            classes='table table-striped"', justify='left'
        )

    def test_find_runs_for_manual_review(self, gen_funcs, test_df_for_manual_review):
        """
        Test runs for manual review are found correctly
        """
        review_dict = gen_funcs.find_runs_for_manual_review(test_df_for_manual_review)

        assert 'RUN_NO_JIRA' in review_dict['no_jira_tix']
        assert 'RUN_JOB_BEFORE_LOG' in review_dict['first_job_before_log']
        # RUN_NO_LOG has upload_time as NaT and is not cancelled/open -> should be in no_log_file
        assert 'RUN_NO_LOG' in review_dict['no_log_file']
        # RUN_NO_FIRST_JOB has first_job as NaT and is not cancelled/open -> should be in no_first_job_found
        assert 'RUN_NO_FIRST_JOB' in review_dict['no_first_job_found']
        assert 'RUN_NO_FINAL_JOB' in review_dict['no_final_job_found']

        # Check that RUN_OK is not in any list
        for key in review_dict:
            assert 'RUN_OK' not in review_dict[key]

    def test_find_runs_for_manual_review_all_ok(self, gen_funcs):
        """
        Test that an empty dict is returned if no runs need manual review.
        """
        ok_run_data = {
            'assay_type': ['CEN'], 'run_name': ['220101_RUN_OK'],
            'upload_time': [pd.Timestamp('2022-01-01 10:00:00')],
            'first_job': [pd.Timestamp('2022-01-01 11:00:00')],
            'processing_finished': [pd.Timestamp('2022-01-01 12:00:00')],
            'jira_status': ['All samples released'],
            'jira_resolved': [pd.Timestamp('2022-01-01 13:00:00')],
            'upload_to_first_job': [0.041667],
            'ticket_key': ['JIRA-OK']
        }
        ok_df = pd.DataFrame(ok_run_data)
        review_dict = gen_funcs.find_runs_for_manual_review(ok_df)
        assert review_dict == {}

    def test_create_assay_objects(self, gen_funcs, test_df_for_stats):
        """
        Test assay objects are created correctly.
        This is more of an integration test for several functions.
        """
        # Use test_df_for_stats which is already an "assay_df" for 'CEN'
        # To make it an "all_assays_df", we can just use it as is,
        # as extract_assay_df will pick up 'CEN' type runs.
        (
            assay_df_out, assay_stats_out, assay_issues_out,
            assay_no_of_002_runs_out, assay_fraction_out,
            assay_percentage_out
        ) = gen_funcs.create_assay_objects(test_df_for_stats, 'CEN')

        assert not assay_df_out.empty
        assert assay_df_out.shape[0] == 4 # All 4 runs are CEN
        assert '<td>Mean overall TAT</td>' in assay_stats_out
        assert assay_issues_out == {} # Assuming test_df_for_stats has no review issues
        assert assay_no_of_002_runs_out == 4
        assert assay_fraction_out == "(3/3) "
        assert assay_percentage_out == 100.0

    def test_add_in_cancelled_runs(self, gen_funcs, all_assays_df_for_cancelled_runs, cancelled_runs_list):
        """
        Test cancelled runs are added, duplicates dropped, and sorted correctly.
        """
        # Ensure 'date' column is not present before calling, or handle its absence if your function expects it
        # For this test setup, 'date' is added inside the function, so it's fine.

        # Define expected columns for df_with_duplicate_data to avoid issues with pd.concat
        # if all_assays_df_for_cancelled_runs doesn't have all columns that cancelled_runs_list implies.
        # The function itself handles missing columns by the nature of pd.concat filling with NaN.
        # However, ensuring 'assay_type' is present for sorting.

        # Make a copy to avoid modifying the fixture
        df_to_modify = all_assays_df_for_cancelled_runs.copy()

        # Add 'ticket_hyperlink' and 'run_date' if they are expected by the drop in write_to_csv later
        # or ensure the function add_in_cancelled_runs handles their absence.
        # Based on the function, these are not strictly needed as inputs for add_in_cancelled_runs.

        result_df = gen_funcs.add_in_cancelled_runs(df_to_modify, cancelled_runs_list)

        assert result_df.shape[0] == 3 # 2 original + 1 new cancelled (1 duplicate cancelled dropped)
        assert '220103_RUN3_CANCELLED' in result_df['run_name'].values
        # Check that the duplicate '220101_RUN1_ASSAY1' now has the 'Cancelled' status from cancelled_runs_list (last takes precedence)
        assert result_df[result_df['run_name'] == '220101_RUN1_ASSAY1'].iloc[0]['jira_status'] == 'Cancelled'
        assert result_df.iloc[0]['run_name'] == '220101_RUN1_ASSAY1' # Sorted by date within ASSAY1
        assert result_df.iloc[1]['run_name'] == '220102_RUN2_ASSAY1'
        assert result_df.iloc[2]['run_name'] == '220103_RUN3_CANCELLED'
        assert 'date' not in result_df.columns # 'date' column should be dropped

    def test_write_to_csv(self, gen_funcs, tmp_path, all_assays_df_for_cancelled_runs):
        """
        Test DataFrame is written to CSV correctly, and specific columns are dropped.
        """
        # Add columns that are supposed to be dropped to ensure they are handled
        df_to_write = all_assays_df_for_cancelled_runs.copy() # Start with a base df
        df_to_write['change_log'] = 'some_log_data' # Expected to be present from fixture
        df_to_write['ticket_hyperlink'] = 'some_hyperlink_data' # Add column to be dropped
        df_to_write['run_date'] = pd.to_datetime('2022-01-01') # Add column to be dropped

        # Temporarily change audit_start and audit_end for predictable filename
        original_audit_start = gen_funcs.audit_start
        original_audit_end = gen_funcs.audit_end
        gen_funcs.audit_start = "teststart"
        gen_funcs.audit_end = "testend"

        # Call the function - it writes to current dir, so use tmp_path by chdir or mocking open
        # For simplicity, we'll let it write to the default location and check if the file is created
        # and then clean up. A better approach for unit tests is to mock `open` or use `tmp_path`.
        # However, the function writes to a filename based on audit_start/end.
        # Let's assume the function writes to a path relative to ROOT_DIR or current dir.
        # For this test, we'll check if the file exists in the default location (which might be tricky in CI).
        # A robust way: mock 'to_csv' or make the path an argument.
        # Given the current structure, we'll rely on the default behavior and make filename predictable.

        output_filename = f"audit_info_{gen_funcs.audit_start}_{gen_funcs.audit_end}.csv"
        output_file = tmp_path / output_filename

        # Mocking to_csv is cleaner:
        written_df = []
        def mock_to_csv(df, path, float_format, index):
            written_df.append(df.copy()) # Capture the DataFrame that would be written
            # Simulate file write if needed for other checks, e.g. with open(path, 'w') as f: f.write("dummy")

        original_to_csv = pd.DataFrame.to_csv
        pd.DataFrame.to_csv = lambda self, path, float_format, index: mock_to_csv(self, path, float_format, index)


        gen_funcs.write_to_csv(df_to_write)

        # Restore original to_csv to avoid affecting other tests
        pd.DataFrame.to_csv = original_to_csv
        gen_funcs.audit_start = original_audit_start
        gen_funcs.audit_end = original_audit_end

        assert len(written_df) == 1 # Ensure to_csv was called once
        df_that_was_written = written_df[0]

        assert 'change_log' not in df_that_was_written.columns
        assert 'ticket_hyperlink' not in df_that_was_written.columns
        assert 'run_date' not in df_that_was_written.columns
        # Check that other essential columns are still there
        assert 'run_name' in df_that_was_written.columns
        assert 'assay_type' in df_that_was_written.columns


    def test_create_run_df_missing_datetime_cols(self, gen_funcs):
        """
        Test create_run_df when some datetime columns are missing from the input dict.
        The function should add them as NaT series.
        """
        test_dict = {
            '220101_RUN1': {
                'assay_type': 'CEN',
                'run_name': '220101_RUN1', # run_name usually from dict key
                'upload_time': '2022-01-01 10:00:00',
                # 'first_job' is missing
                'processing_finished': '2022-01-01 12:00:00',
                # 'jira_resolved' is missing
                'jira_status': 'Open',
                'ticket_key': 'key1'
            }
        }
        # Manually add run_name to inner dict if create_run_df expects it,
        # though .assign(run_name=run_dict.keys()) handles it.
        # The provided function structure for create_run_df handles run_name assignment.

        df = gen_funcs.create_run_df(test_dict)

        assert 'first_job' in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df['first_job'])
        assert df['first_job'].isnull().all()

        assert 'jira_resolved' in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df['jira_resolved'])
        assert df['jira_resolved'].isnull().all()

        # Check existing datetime columns are processed
        assert pd.api.types.is_datetime64_any_dtype(df['upload_time'])
        assert not df['upload_time'].isnull().all()
        assert pd.api.types.is_datetime64_any_dtype(df['processing_finished'])
        assert not df['processing_finished'].isnull().all()
