import json
import pytest
from unittest.mock import patch, MagicMock

from TAT_audit.utils.dx_requests import DXFunctions
from TAT_audit.utils.dx_requests import dx

# Mock dxpy responses
MOCK_DX_PROJECTS_FILE = "TAT_audit/tests/mock_data/dx/projects.json"
MOCK_DX_JOBS_FILE = "TAT_audit/tests/mock_data/dx/jobs.json"
MOCK_DX_FILES_FILE = "TAT_audit/tests/mock_data/dx/files.json"
MOCK_DX_FOLDERS_FILE = "TAT_audit/tests/mock_data/dx/folders.json"

@pytest.fixture
def dx_functions():
    return DXFunctions()

@pytest.fixture
def mock_dx_projects():
    with open(MOCK_DX_PROJECTS_FILE) as f:
        return json.load(f)

@pytest.fixture
def mock_dx_jobs():
    with open(MOCK_DX_JOBS_FILE) as f:
        return json.load(f)

@pytest.fixture
def mock_dx_files():
    with open(MOCK_DX_FILES_FILE) as f:
        return json.load(f)

@pytest.fixture
def mock_dx_folders():
    with open(MOCK_DX_FOLDERS_FILE) as f:
        return json.load(f)

class TestDXFunctions:
    def test_login_success(self, dx_functions, mocker):
        """Test successful login to DNAnexus."""
        mocker.patch.object(dx, 'set_security_context')
        mocker.patch.object(dx.api, 'system_whoami', return_value=True)

        dx_functions.login("fake_token")

        dx.set_security_context.assert_called_once_with({
            "auth_token_type": "Bearer",
            "auth_token": "fake_token"
        })
        dx.api.system_whoami.assert_called_once()

    def test_login_failure(self, dx_functions, mocker):
        """Test failed login to DNAnexus."""
        mocker.patch.object(dx, 'set_security_context')
        mocker.patch.object(dx.api, 'system_whoami', side_effect=Exception("Login failed"))

        with pytest.raises(SystemExit) as excinfo:
            dx_functions.login("fake_token")

        assert excinfo.value.code == 1
        dx.set_security_context.assert_called_once_with({
            "auth_token_type": "Bearer",
            "auth_token": "fake_token"
        })
        dx.api.system_whoami.assert_called_once()

    def test_get_002_projects_within_buffer_period(self, dx_functions, mocker, mock_dx_projects):
        """Test getting 002 projects within the buffer period."""
        mocker.patch.object(dx, 'find_projects', return_value=mock_dx_projects["projects_dx_response"])

        assay_types = ["CEN", "TSO500"]
        five_days_after = "2023-03-15"
        five_days_before_start = "2023-03-01"

        result = dx_functions.get_002_projects_within_buffer_period(assay_types, five_days_after, five_days_before_start)

        dx.find_projects.assert_called_once_with(
            level='VIEW',
            created_before=five_days_after,
            created_after=five_days_before_start,
            name=f"^002.*({'|'.join(assay_types)})$",
            name_mode="regexp",
            describe={'fields': {'id': True, 'name': True}}
        )
        assert result == mock_dx_projects["projects_dx_response"]

    def test_get_staging_folders(self, dx_functions, mocker, mock_dx_folders):
        """Test getting staging folders."""
        mocker.patch.object(dx.dxfile_functions, 'list_subfolders', return_value=mock_dx_folders["staging_folder_names"])

        staging_id = "project-xxxx"
        result = dx_functions.get_staging_folders(staging_id)

        dx.dxfile_functions.list_subfolders.assert_called_once_with(
            project=staging_id,
            path='/',
            recurse=False
        )
        assert result == mock_dx_folders["expected_staging_folders"]

    def test_find_log_file_in_folder(self, dx_functions, mocker, mock_dx_files):
        """Test finding log files in a folder."""
        mocker.patch.object(dx, 'find_data_objects', return_value=mock_dx_files["log_file_info"])

        run_name = "RUN001"
        staging_id = "project-xxxx"
        result = dx_functions.find_log_file_in_folder(run_name, staging_id)

        dx.find_data_objects.assert_called_once_with(
            project=staging_id,
            folder=f'/{run_name}/runs',
            name="*.lane.all.log",
            name_mode='glob',
            classname='file',
            describe={'fields': {'name': True, 'created': True}}
        )
        assert result == mock_dx_files["log_file_info"]

    def test_find_conductor_jobs(self, dx_functions, mocker, mock_dx_jobs):
        """Test finding conductor jobs."""
        mocker.patch.object(dx.search, 'find_jobs', return_value=mock_dx_jobs["conductor_jobs_response"])

        staging_id = "project-xxxx"
        five_days_after = "2023-03-15"
        five_days_before_start = "2023-03-01"

        result = dx_functions.find_conductor_jobs(staging_id, five_days_after, five_days_before_start)

        dx.search.find_jobs.assert_called_once_with(
            project=staging_id,
            created_before=five_days_after,
            created_after=five_days_before_start,
            name='eggd_conductor*',
            name_mode='glob',
            describe={'fields': {'id': True, 'name': True, 'created': True, 'originalInput': True}}
        )
        assert result == mock_dx_jobs["conductor_jobs_response"]

    def test_search_for_final_jobs(self, dx_functions, mocker, mock_dx_jobs):
        """Test searching for final jobs."""
        mocker.patch.object(dx.search, 'find_jobs', return_value=mock_dx_jobs["final_jobs_response"])

        project_id = "project-yyyy"
        job_name_to_search = "eggd_multiqc"

        result = dx_functions.search_for_final_jobs(project_id, job_name_to_search)

        dx.search.find_jobs.assert_called_once_with(
            project=project_id,
            state='done',
            name=f"*{job_name_to_search}*",
            name_mode='glob',
            describe={'fields': {'id': True, 'project': True, 'name': True, 'executableName': True, 'stoppedRunning': True}}
        )
        assert result == mock_dx_jobs["final_jobs_response"]

    def test_create_run_dictionary(self, dx_functions, mock_dx_projects):
        """Test creating a run dictionary from DNAnexus project data."""
        from_date_obj = MagicMock()
        from_date_obj.strftime.return_value = "230301" # Corresponds to 2023-03-01
        to_date_obj = MagicMock()
        to_date_obj.strftime.return_value = "230310"   # Corresponds to 2023-03-10

        expected_run_dict = {
            '230305_A01295_0100_AHAPPYFLOW': {
                'project_id': 'project-GZJ4V5Q0J4xQyZqkY0X8PffX',
                'assay_type': 'CEN'
            },
            '230302_M00123_0050_AANOTHERGO': {
                'project_id': 'project-GYq0j1j0J4x9pBkkXyQ8QZ1B',
                'assay_type': 'TSO500'
            }
        }
        # Note: projects.json has two projects, one with date 230305 and another 230302
        # Both are within the 230301-230310 range.

        result = dx_functions.create_run_dictionary(mock_dx_projects["projects_dx_response"], from_date_obj, to_date_obj)

        assert result == expected_run_dict

    def test_create_run_dictionary_filters_dates(self, dx_functions, mock_dx_projects):
        """Test that create_run_dictionary filters projects based on date in name."""
        from_date_obj = MagicMock()
        from_date_obj.strftime.return_value = "230303" # Corresponds to 2023-03-03
        to_date_obj = MagicMock()
        to_date_obj.strftime.return_value = "230306"   # Corresponds to 2023-03-06

        # Only the project with date 230305 should be included
        expected_run_dict = {
            '230305_A01295_0100_AHAPPYFLOW': {
                'project_id': 'project-GZJ4V5Q0J4xQyZqkY0X8PffX',
                'assay_type': 'CEN'
            }
        }

        result = dx_functions.create_run_dictionary(mock_dx_projects["projects_dx_response"], from_date_obj, to_date_obj)
        assert result == expected_run_dict

    def test_create_run_dictionary_handles_vaf_checks(self, dx_functions):
        """Test that create_run_dictionary ignores vaf_check projects."""
        from_date_obj = MagicMock()
        from_date_obj.strftime.return_value = "230301"
        to_date_obj = MagicMock()
        to_date_obj.strftime.return_value = "230310"

        mock_projects_with_vaf = [
            {
                "describe": {
                    "id": "project-GZJ4V5Q0J4xQyZqkY0X8PffX",
                    "name": "002_230305_vaf_check_AHAPPYFLOW_CEN" # vaf in name
                },
                "id": "project-GZJ4V5Q0J4xQyZqkY0X8PffX",
            },
            {
                "describe": {
                    "id": "project-GYq0j1j0J4x9pBkkXyQ8QZ1B",
                    "name": "002_230302_M00123_0050_AANOTHERGO_TSO500"
                },
                "id": "project-GYq0j1j0J4x9pBkkXyQ8QZ1B",
            }
        ]

        expected_run_dict = {
            '230302_M00123_0050_AANOTHERGO': { # Only the non-vaf project
                'project_id': 'project-GYq0j1j0J4x9pBkkXyQ8QZ1B',
                'assay_type': 'TSO500'
            }
        }
        result = dx_functions.create_run_dictionary(mock_projects_with_vaf, from_date_obj, to_date_obj)
        assert result == expected_run_dict


    @patch('TAT_audit.utils.dx_requests.Levenshtein.distance')
    def test_update_run_name(self, mock_levenshtein_distance, dx_functions):
        """Test updating run names and identifying typos."""
        mock_levenshtein_distance.side_effect = [0, 1, 3] # No typo, 1 diff typo, >2 diff (no update)

        run_dict_input = {
            "RUN001_IDENTICAL": {"run_folder_name": "RUN001_IDENTICAL", "assay_type": "CEN"},
            "RUN002_ORIGINAL": {"run_folder_name": "RUN002_TYPO", "assay_type": "TSO500"}, # Levenshtein will return 1
            "RUN003_WAYOFF": {"run_folder_name": "RUN003_FOLDER", "assay_type": "MYE"}, # Levenshtein will return 3
            "RUN004_NOFOLDER": {"assay_type": "TWE"} # No run_folder_name
        }

        expected_updated_dict = {
            "RUN001_IDENTICAL": {"run_folder_name": "RUN001_IDENTICAL", "assay_type": "CEN"},
            "RUN002_TYPO": {"run_folder_name": "RUN002_TYPO", "assay_type": "TSO500"}, # Key updated to folder name
            "RUN003_WAYOFF": {"run_folder_name": "RUN003_FOLDER", "assay_type": "MYE"}, # Key not updated
            "RUN004_NOFOLDER": {"assay_type": "TWE"}
        }
        expected_typo_list = [
            {'assay_type': 'TSO500', 'folder_name': 'RUN002_TYPO', 'project_name_002': 'RUN002_ORIGINAL'}
        ]

        updated_dict, typo_list = dx_functions.update_run_name(run_dict_input)

        assert updated_dict == expected_updated_dict
        assert typo_list == expected_typo_list
        assert mock_levenshtein_distance.call_count == 3 # Called for RUN001, RUN002, RUN003

    def test_get_log_file_created_time(self, dx_functions, mock_dx_files, mocker):
        """Test getting log file created time."""
        # mock_dx_files["log_file_info"][0]["describe"]["created"] is 1678280000000
        # This corresponds to 2023-03-08 12:53:20 UTC if GTM+0
        # Python's time.localtime will convert to local time. We need to control this.

        # We mock time.strftime to ensure consistent output regardless of test environment's timezone
        # The value 1678280000.0 (from 1678280000000 / 1000) will be passed to time.localtime
        # We make strftime return a fixed string when called with the result of localtime(1678280000.0)

        mocker.patch('time.strftime', return_value="2023-03-08 12:53:20")
        mocker.patch('time.localtime') # To verify it's called

        expected_time = "2023-03-08 12:53:20"
        result = dx_functions.get_log_file_created_time(mock_dx_files["log_file_info"])

        time.localtime.assert_called_once_with(1678280000.0)
        time.strftime.assert_called_once_with('%Y-%m-%d %H:%M:%S', time.localtime.return_value)
        assert result == expected_time

    @patch('TAT_audit.utils.dx_requests.Levenshtein.distance')
    def test_add_upload_time(self, mock_levenshtein_distance, dx_functions, mock_dx_folders, mock_dx_files, mocker):
        """Test adding upload time to the run dictionary."""
        # Levenshtein will be called for each run_name against each folder_name until a match (dist <=2)
        # RUN_EXISTS_IN_STAGING: match with "RUN_EXISTS_IN_STAGING_FOLDER" (dist 0)
        # RUN_TYPO_IN_STAGING: match with "RUN_TYPO_IN_STAGING_FLODER" (dist 1) - folder name has typo
        # RUN_NOT_IN_STAGING: no match (dist > 2 for all)

        mock_levenshtein_distance.side_effect = [
            0, # RUN_EXISTS_IN_STAGING vs RUN_EXISTS_IN_STAGING_FOLDER
            1, # RUN_TYPO_IN_STAGING vs RUN_TYPO_IN_STAGING_FLODER
            5, # RUN_NOT_IN_STAGING vs RUN_EXISTS_IN_STAGING_FOLDER
            5, # RUN_NOT_IN_STAGING vs RUN_TYPO_IN_STAGING_FLODER
        ]

        # Mock find_log_file_in_folder and get_log_file_created_time
        mock_find_log = mocker.patch.object(dx_functions, 'find_log_file_in_folder')
        mock_get_time = mocker.patch.object(dx_functions, 'get_log_file_created_time')

        # Let find_log_file_in_folder return a valid response for the first two, empty for others
        mock_find_log.side_effect = [mock_dx_files["log_file_info"], mock_dx_files["log_file_info"], []]
        # Let get_log_file_created_time return a fixed time
        mock_get_time.return_value = "2023-01-01 10:00:00"

        run_dict_input = {
            "RUN_EXISTS_IN_STAGING": {},
            "RUN_TYPO_IN_STAGING": {},
            "RUN_NOT_IN_STAGING": {}
        }
        staging_folders_input = ["RUN_EXISTS_IN_STAGING_FOLDER", "RUN_TYPO_IN_STAGING_FLODER"] # Note typo in second folder
        staging_id_input = "project-stagingid"

        expected_run_dict = {
            "RUN_EXISTS_IN_STAGING": {
                "run_folder_name": "RUN_EXISTS_IN_STAGING_FOLDER",
                "upload_time": "2023-01-01 10:00:00"
            },
            "RUN_TYPO_IN_STAGING": {
                "run_folder_name": "RUN_TYPO_IN_STAGING_FLODER", # Matched with typo
                "upload_time": "2023-01-01 10:00:00"
            },
            "RUN_NOT_IN_STAGING": {} # No upload time as no matching folder or log file
        }

        result_dict = dx_functions.add_upload_time(staging_folders_input, run_dict_input, staging_id_input)

        assert result_dict == expected_run_dict
        # Check Levenshtein calls
        # RUN_EXISTS_IN_STAGING vs RUN_EXISTS_IN_STAGING_FOLDER (dist 0 - match)
        # RUN_TYPO_IN_STAGING vs RUN_EXISTS_IN_STAGING_FOLDER (dist >2 assumed by mock_levenshtein_distance if not the first call for it)
        # RUN_TYPO_IN_STAGING vs RUN_TYPO_IN_STAGING_FLODER (dist 1 - match)
        # RUN_NOT_IN_STAGING vs RUN_EXISTS_IN_STAGING_FOLDER (dist 5)
        # RUN_NOT_IN_STAGING vs RUN_TYPO_IN_STAGING_FLODER (dist 5)
        # Expected Levenshtein calls:
        calls_lev = [
            mocker.call("RUN_EXISTS_IN_STAGING_FOLDER", "RUN_EXISTS_IN_STAGING"),
            mocker.call("RUN_TYPO_IN_STAGING_FLODER", "RUN_TYPO_IN_STAGING"), # This will be the second call to Levenshtein due to loop structure
            mocker.call("RUN_EXISTS_IN_STAGING_FOLDER", "RUN_NOT_IN_STAGING"),
            mocker.call("RUN_TYPO_IN_STAGING_FLODER", "RUN_NOT_IN_STAGING"),
        ]
        # The exact order of calls to Levenshtein depends on the iteration order of run_dict.keys() and staging_folders.
        # For simplicity, we'll just check the count if the logic is complex to trace exactly.
        # For this test setup, it should be 4 calls as described above.
        assert mock_levenshtein_distance.call_count == 4


        # Check find_log_file_in_folder calls
        calls_find_log = [
            mocker.call("RUN_EXISTS_IN_STAGING_FOLDER", staging_id_input),
            mocker.call("RUN_TYPO_IN_STAGING_FLODER", staging_id_input)
        ]
        mock_find_log.assert_has_calls(calls_find_log, any_order=False) # Order matters here as side_effect is a list
        assert mock_find_log.call_count == 2 # Only called when a folder match is found

        # Check get_log_file_created_time calls
        calls_get_time = [
            mocker.call(mock_dx_files["log_file_info"]),
            mocker.call(mock_dx_files["log_file_info"])
        ]
        mock_get_time.assert_has_calls(calls_get_time, any_order=False)
        assert mock_get_time.call_count == 2 # Only called when log files are found

    def test_get_earliest_conductor_job_for_each_run(self, dx_functions, mock_dx_jobs):
        """Test getting the earliest conductor job for each run."""
        # mock_dx_jobs["conductor_jobs_response"] has one job:
        # name: "eggd_conductor-RUN001", created: 1678280000000 (i.e., 1678280000.0 after /1000)

        # Add another job for RUN001, but earlier
        conductor_jobs_input = mock_dx_jobs["conductor_jobs_response"] + [
            {
                "describe": {
                    "id": "job-EARLIER",
                    "name": "eggd_conductor-RUN001", # Same run
                    "created": 1678270000000, # Earlier time
                    "originalInput": {}
                },
                "id": "job-EARLIER"
            },
            {
                "describe": {
                    "id": "job-RUN002",
                    "name": "eggd_conductor-RUN002", # Different run
                    "created": 1678290000000,
                    "originalInput": {}
                },
                "id": "job-RUN002"
            },
            {
                "describe": {
                    "id": "job-MALFORMED",
                    "name": "eggd_conductor_MALFORMED_NO_RUN_NAME_HERE", # Malformed name
                    "created": 1678295000000,
                    "originalInput": {}
                },
                "id": "job-MALFORMED"
            }
        ]

        expected_dict = {
            "RUN001": 1678270000.0, # Earlier time for RUN001
            "RUN002": 1678290000.0,
            "eggd_conductor_MALFORMED_NO_RUN_NAME_HERE": 1678295000.0 # Uses full name if parse fails
        }

        result = dx_functions.get_earliest_conductor_job_for_each_run(conductor_jobs_input)
        assert result == expected_dict

    def test_add_first_job_time(self, dx_functions, mocker):
        """Test adding the first job time to the run dictionary."""
        mocker.patch('time.strftime', lambda fmt, tm: f"formatted_time_for_{tm}")

        # conductor_job_dict: run_name -> earliest_conductor_job_start_epoch_float
        conductor_job_dict_input = {
            "RUN001_MATCH_AFTER_UPLOAD": 1678280000.0, # time.localtime(1678280000.0) -> formatted_time_for_1678280000.0
            "RUN002_MATCH_BEFORE_UPLOAD": 1678270000.0,
            "RUN003_NO_UPLOAD_TIME": 1678290000.0,
            "RUN004_NOT_IN_RUNDICT": 1678300000.0
        }

        run_dict_input = {
            "RUN001_MATCH_AFTER_UPLOAD": {"upload_time": "formatted_time_for_1678275000.0"}, # Upload time is before job
            "RUN002_MATCH_BEFORE_UPLOAD": {"upload_time": "formatted_time_for_1678275000.0"}, # Upload time is AFTER job
            "RUN003_NO_UPLOAD_TIME": {}, # No 'upload_time' key
            # RUN004_NOT_IN_RUNDICT is not a key here
        }

        expected_run_dict = {
            "RUN001_MATCH_AFTER_UPLOAD": {
                "upload_time": "formatted_time_for_1678275000.0",
                "first_job": "formatted_time_for_1678280000.0" # Added
            },
            "RUN002_MATCH_BEFORE_UPLOAD": { # Not added, job time is before upload time
                "upload_time": "formatted_time_for_1678275000.0"
            },
            "RUN003_NO_UPLOAD_TIME": {}, # Not added, no upload time
        }

        # Mock time.strftime to check its calls for the valid case
        mock_strftime = mocker.patch('time.strftime')
        mock_strftime.return_value = "formatted_time_for_1678280000.0" # For RUN001

        result_dict = dx_functions.add_first_job_time(conductor_job_dict_input, run_dict_input)

        assert result_dict == expected_run_dict
        # Check that time.strftime was called for RUN001's job time
        # time.localtime would be called with 1678280000.0
        mock_strftime.assert_called_once_with('%Y-%m-%d %H:%M:%S', mocker.ANY)


    def test_get_last_job(self, dx_functions, mock_dx_jobs, mocker):
        """Test getting the last job completion time."""
        # mock_dx_jobs["final_jobs_response"] has one job: stoppedRunning: 1678290000000

        # Add more jobs to test max()
        final_jobs_input = mock_dx_jobs["final_jobs_response"] + [
            {"describe": {"stoppedRunning": 1678300000000}}, # Later
            {"describe": {"stoppedRunning": 1678285000000}}  # Earlier
        ]

        mocker.patch('time.strftime', return_value="formatted_latest_time")
        mocker.patch('time.localtime')

        result = dx_functions.get_last_job(final_jobs_input)

        time.localtime.assert_called_once_with(1678300000.0) # Max epoch time / 1000
        time.strftime.assert_called_once_with('%Y-%m-%d %H:%M:%S', time.localtime.return_value)
        assert result == "formatted_latest_time"

    def test_get_last_job_no_jobs(self, dx_functions):
        """Test get_last_job when no jobs are provided."""
        assert dx_functions.get_last_job([]) is None

    def test_get_final_job_before_ticket_resolved(self, dx_functions, mock_dx_jobs, mocker):
        """Test getting the final job completed before Jira ticket resolution."""
        # JIRA resolved timestamp: "2023-03-08 18:00:00" -> epoch 1678298400.0
        jira_resolved_ts = "2023-03-08 18:00:00"

        # mock_dx_jobs["final_jobs_response"][0]["describe"]["stoppedRunning"] is 1678290000000 (before resolution)
        # Job 2: 1678300000000 (after resolution)
        # Job 3: 1678295000000 (before resolution, and latest of those before)
        final_jobs_input = [
            {"describe": {"stoppedRunning": 1678290000000}}, # kept (job from mock_dx_jobs)
            {"describe": {"stoppedRunning": 1678300000000}}, # filtered out
            {"describe": {"stoppedRunning": 1678295000000}}  # kept, this one is chosen
        ]

        mocker.patch('time.strftime', return_value="formatted_correct_job_time")
        mocker.patch('time.localtime')
        # Mock time.mktime and time.strptime for converting jira_resolved_ts
        mocker.patch('time.mktime', return_value=1678298400.0) # Mocked epoch for "2023-03-08 18:00:00"
        mocker.patch('time.strptime')

        result = dx_functions.get_final_job_before_ticket_resolved(final_jobs_input, jira_resolved_ts)

        time.strptime.assert_called_once_with(jira_resolved_ts, "%Y-%m-%d %H:%M:%S")
        time.mktime.assert_called_once_with(time.strptime.return_value)
        time.localtime.assert_called_once_with(1678295000.0) # Max of jobs before resolution
        time.strftime.assert_called_once_with('%Y-%m-%d %H:%M:%S', time.localtime.return_value)
        assert result == "formatted_correct_job_time"

    def test_get_final_job_before_ticket_resolved_no_valid_jobs(self, dx_functions, mock_dx_jobs, mocker):
        """Test get_final_job_before_ticket_resolved when no jobs are before resolution."""
        jira_resolved_ts = "2023-03-01 00:00:00" # Very early
        mocker.patch('time.mktime', return_value=1677628800.0)
        mocker.patch('time.strptime')

        # All jobs in mock_dx_jobs["final_jobs_response"] are after this date
        assert dx_functions.get_final_job_before_ticket_resolved(mock_dx_jobs["final_jobs_response"], jira_resolved_ts) is None

    def test_get_final_job_before_ticket_resolved_no_jobs_input(self, dx_functions, mocker):
        """Test get_final_job_before_ticket_resolved with empty job list."""
        jira_resolved_ts = "2023-03-08 18:00:00"
        mocker.patch('time.mktime', return_value=1678298400.0) # Doesn't really matter here
        mocker.patch('time.strptime')
        assert dx_functions.get_final_job_before_ticket_resolved([], jira_resolved_ts) is None

    @patch('TAT_audit.utils.dx_requests.DXFunctions.search_for_final_jobs')
    @patch('TAT_audit.utils.dx_requests.DXFunctions.get_final_job_before_ticket_resolved')
    @patch('TAT_audit.utils.dx_requests.DXFunctions.get_last_job')
    def test_add_last_job_time(self, mock_get_last_job, mock_get_final_job_resolved, mock_search_final_jobs, dx_functions):
        """Test adding the last job time to the run dictionary."""
        run_dict_input = {
            "RUN001_RESOLVED": {"project_id": "proj1", "assay_type": "CEN", "jira_resolved": "2023-01-01 12:00:00"},
            "RUN002_NOT_RESOLVED": {"project_id": "proj2", "assay_type": "TSO500"}, # No jira_resolved
            "RUN003_NO_JOB_TO_SEARCH": {"project_id": "proj3", "assay_type": "MYE"}, # last_jobs won't have MYE
            "RUN004_JOB_FOUND_RESOLVED": {"project_id": "proj4", "assay_type": "TWE", "jira_resolved": "2023-01-02 12:00:00"},
            "RUN005_JOB_FOUND_NOT_RESOLVED": {"project_id": "proj5", "assay_type": "CEN"},
            "RUN006_NO_FINAL_JOB_FOUND_RESOLVED": {"project_id": "proj6", "assay_type": "TSO500", "jira_resolved": "2023-01-03 12:00:00"},
            "RUN007_NO_FINAL_JOB_FOUND_NOT_RESOLVED": {"project_id": "proj7", "assay_type": "TWE"},
        }
        last_jobs_config = {"CEN": "eggd_artemis", "TSO500": "eggd_MultiQC", "TWE": "eggd_generate_variant_workbook"}

        # Mock return values
        mock_search_final_jobs.side_effect = [
            ["job_data1"], # RUN001
            ["job_data2"], # RUN002
            # RUN003 - search_for_final_jobs not called as 'MYE' not in last_jobs_config for job_to_search
            ["job_data4"], # RUN004
            ["job_data5"], # RUN005
            [],            # RUN006 (no jobs found by search)
            [],            # RUN007 (no jobs found by search)
        ]
        mock_get_final_job_resolved.side_effect = ["time_resolved1", "time_resolved4", None] # For RUN001, RUN004, RUN006(returns None)
        mock_get_last_job.side_effect = ["time_not_resolved2", "time_not_resolved5", None] # For RUN002, RUN005, RUN007(returns None)

        expected_run_dict = {
            "RUN001_RESOLVED": {"project_id": "proj1", "assay_type": "CEN", "jira_resolved": "2023-01-01 12:00:00", "processing_finished": "time_resolved1"},
            "RUN002_NOT_RESOLVED": {"project_id": "proj2", "assay_type": "TSO500", "processing_finished": "time_not_resolved2"},
            "RUN003_NO_JOB_TO_SEARCH": {"project_id": "proj3", "assay_type": "MYE"},
            "RUN004_JOB_FOUND_RESOLVED": {"project_id": "proj4", "assay_type": "TWE", "jira_resolved": "2023-01-02 12:00:00", "processing_finished": "time_resolved4"},
            "RUN005_JOB_FOUND_NOT_RESOLVED": {"project_id": "proj5", "assay_type": "CEN", "processing_finished": "time_not_resolved5"},
            "RUN006_NO_FINAL_JOB_FOUND_RESOLVED": {"project_id": "proj6", "assay_type": "TSO500", "jira_resolved": "2023-01-03 12:00:00"}, # No processing_finished
            "RUN007_NO_FINAL_JOB_FOUND_NOT_RESOLVED": {"project_id": "proj7", "assay_type": "TWE"}, # No processing_finished
        }

        result_dict = dx_functions.add_last_job_time(run_dict_input, last_jobs_config)
        assert result_dict == expected_run_dict

        # Verify calls to mocks
        assert mock_search_final_jobs.call_count == 6 # Not called for MYE
        mock_search_final_jobs.assert_any_call("proj1", "eggd_artemis")
        mock_search_final_jobs.assert_any_call("proj7", "eggd_generate_variant_workbook")

        assert mock_get_final_job_resolved.call_count == 3
        mock_get_final_job_resolved.assert_any_call(["job_data1"], "2023-01-01 12:00:00")
        mock_get_final_job_resolved.assert_any_call([], "2023-01-03 12:00:00") # For RUN006

        assert mock_get_last_job.call_count == 3
        mock_get_last_job.assert_any_call(["job_data2"])
        mock_get_last_job.assert_any_call([]) # For RUN007
    # More tests will be added here in subsequent subtasks
