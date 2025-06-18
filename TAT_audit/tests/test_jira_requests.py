import json
import pytest
from unittest.mock import patch, MagicMock, call
import datetime as dt

from TAT_audit.utils.jira_requests import JiraFunctions
from requests.auth import HTTPBasicAuth

# Mock Jira API responses
MOCK_JIRA_TICKETS_FILE = "TAT_audit/tests/mock_data/jira/tickets.json"
MOCK_JIRA_CHANGELOGS_FILE = "TAT_audit/tests/mock_data/jira/changelogs.json"

@pytest.fixture
def mock_jira_tickets():
    with open(MOCK_JIRA_TICKETS_FILE) as f:
        return json.load(f)

@pytest.fixture
def mock_jira_changelogs():
    with open(MOCK_JIRA_CHANGELOGS_FILE) as f:
        return json.load(f)

@pytest.fixture
def jira_functions_instance(mocker):
    # Basic parameters for JiraFunctions initialization
    mock_dt = mocker.patch('TAT_audit.utils.jira_requests.dt') # Mock datetime within the module

    # Setup specific return values if needed by tests that use this fixture directly
    # For now, assume default MagicMock behavior is fine for dt.datetime.strptime

    return JiraFunctions(
        jira_email="test@example.com",
        jira_token="fake_token",
        assay_types=["CEN", "TSO500"],
        cancelled_statuses=["Cancelled"],
        audit_start_obj=MagicMock(),
        audit_end_obj=MagicMock(),
        open_statuses=["Open"],
        five_days_before_start="2023-01-01",
        five_days_after="2023-01-31"
    )

class TestJiraFunctions:

    def test_init(self, mocker):
        """Test JiraFunctions initialization."""
        mock_auth_constructor = mocker.patch('TAT_audit.utils.jira_requests.HTTPBasicAuth')

        jira_email = "user@example.com"
        jira_token = "apitoken"
        assay_types = ["MYE"]
        cancelled_statuses = ["Cancelled By User"]
        audit_start_obj = dt.datetime(2023, 1, 1)
        audit_end_obj = dt.datetime(2023, 1, 31)
        open_statuses = ["In Progress"]
        five_days_before_start_str = "2022-12-27"
        five_days_after_str = "2023-02-05"

        jf = JiraFunctions(
            jira_email, jira_token, assay_types, cancelled_statuses,
            audit_start_obj, audit_end_obj, open_statuses,
            five_days_before_start_str, five_days_after_str
        )

        assert jf.jira_email == jira_email
        assert jf.jira_token == jira_token
        mock_auth_constructor.assert_called_once_with(jira_email, jira_token)
        assert jf.auth == mock_auth_constructor.return_value
        assert jf.headers == {"Accept": "application/json"}
        assert jf.assay_types == assay_types
        assert jf.cancelled_statuses == cancelled_statuses
        assert jf.audit_start_obj == audit_start_obj
        assert jf.audit_end_obj == audit_end_obj
        assert jf.open_statuses == open_statuses
        assert jf.five_days_before_start == five_days_before_start_str
        assert jf.five_days_after == five_days_after_str

    @patch('TAT_audit.utils.jira_requests.requests.request')
    def test_query_jira_tickets_in_queue_single_page(self, mock_request, jira_functions_instance, mock_jira_tickets):
        """Test querying Jira tickets when all results fit in a single page."""
        mock_response = MagicMock()
        mock_response.ok = True
        # Ensure 'values' is part of the structure even if empty for the stop condition
        mock_response.text = json.dumps({"values": mock_jira_tickets["single_page_response"], "isLast": True, "size": 50, "start": 0})

        # Second call to simulate end of pagination
        mock_response_empty = MagicMock()
        mock_response_empty.ok = True
        mock_response_empty.text = json.dumps({"values": [], "isLast": True, "size": 0, "start": 50})

        mock_request.side_effect = [mock_response, mock_response_empty]

        queue_id = 35
        result = jira_functions_instance.query_jira_tickets_in_queue(queue_id)

        expected_url = f"https://cuhbioinformatics.atlassian.net/rest/servicedeskapi/servicedesk/4/queue/{queue_id}/issue"
        calls = [
            call("GET", url=f"{expected_url}?start=0", headers=jira_functions_instance.headers, auth=jira_functions_instance.auth),
            call("GET", url=f"{expected_url}?start=50", headers=jira_functions_instance.headers, auth=jira_functions_instance.auth)
        ]
        mock_request.assert_has_calls(calls)
        assert result == mock_jira_tickets["single_page_response"]

    @patch('TAT_audit.utils.jira_requests.requests.request')
    def test_query_jira_tickets_in_queue_multiple_pages(self, mock_request, jira_functions_instance, mock_jira_tickets):
        """Test querying Jira tickets with pagination."""
        mock_response_page1 = MagicMock()
        mock_response_page1.ok = True
        mock_response_page1.text = json.dumps({"values": mock_jira_tickets["multi_page_response_p1"], "isLast": False, "size": 1, "start":0}) # Assuming page size of 1 for test simplicity

        mock_response_page2 = MagicMock()
        mock_response_page2.ok = True
        mock_response_page2.text = json.dumps({"values": mock_jira_tickets["multi_page_response_p2"], "isLast": True, "size": 1, "start":1})

        mock_response_empty = MagicMock() # To stop pagination
        mock_response_empty.ok = True
        mock_response_empty.text = json.dumps({"values": [], "isLast":True, "size":0, "start":2})

        mock_request.side_effect = [mock_response_page1, mock_response_page2, mock_response_empty]

        queue_id = 35
        result = jira_functions_instance.query_jira_tickets_in_queue(queue_id)

        expected_url = f"https://cuhbioinformatics.atlassian.net/rest/servicedeskapi/servicedesk/4/queue/{queue_id}/issue"
        # Assuming default page_size is 50, but our mock data implies page_size=1 for simplicity of mock data.
        # The code uses a hardcoded page_size of 50. Let's adjust the test to reflect that.
        # For this test, we will assume the mock data fills up to page_size for simplicity of data.

        # Re-evaluate mock_request.side_effect and expected calls if page_size 50 is strictly tested.
        # For now, this test structure assumes the logic of fetching until 'values' is empty works.
        # If we wanted to test the start=0, start=50, etc. precisely, the mock_jira_tickets needs 50 items per page.

        calls = [
            call("GET", url=f"{expected_url}?start=0", headers=jira_functions_instance.headers, auth=jira_functions_instance.auth),
            call("GET", url=f"{expected_url}?start=50", headers=jira_functions_instance.headers, auth=jira_functions_instance.auth),
            call("GET", url=f"{expected_url}?start=100", headers=jira_functions_instance.headers, auth=jira_functions_instance.auth) # This call will get empty values
        ]
        # Adjusting side_effect based on page_size 50.
        # Page 1: mock_jira_tickets["multi_page_response_p1"] (assume it has 50 items)
        # Page 2: mock_jira_tickets["multi_page_response_p2"] (assume it has <50 items)
        # Page 3: empty

        # Simplified mock for pagination with default page size 50:
        mock_response_page1_50 = MagicMock(); mock_response_page1_50.ok=True
        mock_response_page1_50.text = json.dumps({"values": mock_jira_tickets["multi_page_response_p1"]}) # p1 is first page of 50

        mock_response_page2_50 = MagicMock(); mock_response_page2_50.ok=True
        mock_response_page2_50.text = json.dumps({"values": mock_jira_tickets["multi_page_response_p2"]}) # p2 is second page, could be < 50

        mock_response_empty_50 = MagicMock(); mock_response_empty_50.ok=True
        mock_response_empty_50.text = json.dumps({"values": []}) # Empty to stop

        mock_request.side_effect = [mock_response_page1_50, mock_response_page2_50, mock_response_empty_50]

        result = jira_functions_instance.query_jira_tickets_in_queue(queue_id)

        mock_request.assert_has_calls(calls)
        assert result == mock_jira_tickets["multi_page_response_p1"] + mock_jira_tickets["multi_page_response_p2"]

    @patch('TAT_audit.utils.jira_requests.requests.request')
    def test_query_jira_tickets_in_queue_request_error(self, mock_request, jira_functions_instance):
        """Test querying Jira tickets when the request fails."""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_request.return_value = mock_response

        with pytest.raises(SystemExit) as excinfo:
            jira_functions_instance.query_jira_tickets_in_queue(35)

        assert excinfo.value.code == 1
        mock_request.assert_called_once()

    @patch('TAT_audit.utils.jira_requests.requests.request')
    def test_get_ticket_transition_times(self, mock_request, jira_functions_instance, mock_jira_changelogs):
        """Test getting ticket transition times from Jira changelog."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.text = json.dumps({"values": mock_jira_changelogs["changelog_response"]})
        mock_request.return_value = mock_response

        ticket_id = "21865"
        result = jira_functions_instance.get_ticket_transition_times(ticket_id)

        expected_url = f"https://cuhbioinformatics.atlassian.net/rest/api/3/issue/{ticket_id}/changelog"
        # Asserting that the call was made with URL as a positional argument
        mock_request.assert_called_once_with(
            "GET",
            expected_url, # URL as positional argument
            headers=jira_functions_instance.headers,
            auth=jira_functions_instance.auth
        )
        assert result == mock_jira_changelogs["expected_transitions"]

    @patch('TAT_audit.utils.jira_requests.requests.request')
    def test_get_ticket_transition_times_no_status_changes(self, mock_request, jira_functions_instance):
        """Test get_ticket_transition_times when changelog has no status changes."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.text = json.dumps({"values": [
            {"created": "2023-01-01T10:00:00.000+0000", "items": [{"field": "summary", "toString": "New Summary"}]}
        ]}) # No 'status' field in items
        mock_request.return_value = mock_response

        ticket_id = "123"
        result = jira_functions_instance.get_ticket_transition_times(ticket_id)
        assert result == {} # Expect an empty dict

    def test_create_jira_info_dict(self, jira_functions_instance, mock_jira_tickets, mocker):
        """Test creating a structured dictionary from Jira API response."""
        # Mock datetime.strptime within jira_requests.py for consistent parsing
        # The jira_functions_instance fixture already mocks dt at the module level,
        # so dt.datetime.strptime will be a MagicMock. We need to configure its return value.

        # Prepare side_effect for strptime based on "created" fields in mock_jira_tickets
        # For "single_page_response"[0]: "2024-01-30T16:52:18.000+0000"
        # For "multi_page_response_p1"[0]: "2024-01-30T16:49:38.000+0000"
        # For "multi_page_response_p2"[0]: "2024-01-22T10:00:00.000+0000"

        # We need to ensure that the mock for strptime is correctly accessed via the mocked 'dt' module
        # in jira_functions_instance.
        # The instance's five_days_before_start and five_days_after are strings like "YYYY-MM-DD"
        # The comparison logic in create_jira_info_dict uses dt.datetime.strptime for these too.

        mock_datetime_strptime = jira_functions_instance.audit_start_obj.strptime # Reusing one of the mocked objects for strptime

        # Define specific return values for each call to strptime
        # This needs to match the order of calls in the function for the given input
        # 1. five_days_before_start
        # 2. five_days_after
        # 3. Then for each ticket's 'created' date

        # Let's simplify: assume five_days_before_start and five_days_after allow all tickets.
        # The fixture sets these to "2023-01-01" and "2023-01-31".
        # Our mock tickets are from 2024, so they would be filtered out.
        # We need to adjust the fixture's date range or mock strptime carefully.

        # Let's adjust the instance's date range for this test to include 2024.
        jira_functions_instance.five_days_before_start = "2024-01-01"
        jira_functions_instance.five_days_after = "2024-02-28"

        # Mocking strptime calls for the date range check
        # And then for each ticket's 'created' field.
        def strptime_side_effect(date_string, date_format):
            if date_format == '%Y-%m-%d': # For five_days_before_start / five_days_after
                return dt.datetime.strptime(date_string, date_format)
            elif date_format == '%Y-%m-%d %H:%M:%S': # For ticket 'created'
                 # Remove the 'T' and milliseconds part for parsing
                actual_date_string = date_string.replace('T', ' ').split('.')[0]
                return dt.datetime.strptime(actual_date_string, date_format)
            raise ValueError(f"Unexpected format: {date_format}")

        mock_dt_module = mocker.patch('TAT_audit.utils.jira_requests.dt')
        mock_dt_module.datetime.strptime.side_effect = strptime_side_effect

        # Input combines all mock tickets
        api_response_input = (
            mock_jira_tickets["single_page_response"] +
            mock_jira_tickets["multi_page_response_p1"] +
            mock_jira_tickets["multi_page_response_p2"]
        )

        expected_dict = {
            "240130_A01303_0329_BH2HWHDRX5": {
                'ticket_key': 'EBH-2377', 'ticket_id': '21865',
                'jira_status': 'All samples released', 'assay_type': 'CEN',
                'date_jira_ticket_created': dt.datetime(2024, 1, 30, 16, 52, 18)
            },
            # MYE assay type is not in jira_functions_instance.assay_types, so it will be filtered out.
            # "240130_A01303_0330_AHWL32DRX3" (MYE) should be excluded.
            "240122_A01295_0303_AHTNWYDRX3": { # TWE is not in assay_types ["CEN", "TSO500"]
                'ticket_key': 'EBH-2075', 'ticket_id': '21862',
                'jira_status': 'All samples released', 'assay_type': 'TWE',
                'date_jira_ticket_created': dt.datetime(2024, 1, 22, 10, 0, 0)
            }
        }
        # Filter expected_dict based on assay_types in jira_functions_instance
        expected_dict_filtered = {
            k: v for k, v in expected_dict.items() if v['assay_type'] in jira_functions_instance.assay_types
        }


        result = jira_functions_instance.create_jira_info_dict(api_response_input)

        assert result == expected_dict_filtered
        # Verify strptime calls (simplified check for count)
        # 2 for date range, 3 for tickets = 5 calls that match '%Y-%m-%d %H:%M:%S' or '%Y-%m-%d'
        # The actual number of calls to strptime will be 2 (for boundary dates) + N (for N tickets).
        # N = 3 in this case. So, 5 calls.
        assert mock_dt_module.datetime.strptime.call_count >= 2 # At least for the boundary dates

    def test_create_jira_info_dict_filters_by_date(self, jira_functions_instance, mock_jira_tickets, mocker):
        """Test that create_jira_info_dict filters tickets by date correctly."""
        # Set a narrow date range for the instance
        jira_functions_instance.five_days_before_start = "2024-01-25"
        # Adjust five_days_after to ensure the boundary check includes the full day of 2024-01-30
        # The SUT uses self.five_days_after.split("T")[0] for boundary_end_date, making it midnight.
        # To include tickets from 2024-01-30, boundary_end_date should be end of 2024-01-30 or start of 2024-01-31.
        jira_functions_instance.five_days_after = "2024-01-31" # Ensures boundary_end_date becomes 2024-01-31 00:00:00

        # Explicitly set audit_start_obj and audit_end_obj for the main filtering logic within the audit period
        jira_functions_instance.audit_start_obj = dt.datetime(2024, 1, 25, 0, 0, 0)
        jira_functions_instance.audit_end_obj = dt.datetime(2024, 1, 30, 17, 0, 0) # Precise audit window

        def strptime_side_effect(date_string, date_format):
            if date_string == "2024-01-25" and date_format == '%Y-%m-%d': # For five_days_before_start
                return dt.datetime(2024,1,25)
            # For five_days_after. SUT does .split("T")[0], so date_string will be "2024-01-31" if input is "2024-01-31" or "2024-01-31T..."
            if date_string == "2024-01-31" and date_format == '%Y-%m-%d':
                 return dt.datetime.strptime(date_string, date_format)
            if date_format == '%Y-%m-%d %H:%M:%S':
                 actual_date_string = date_string.replace('T', ' ').split('.')[0]
                 return dt.datetime.strptime(actual_date_string, date_format)
            # Fallback for other calls if any, or raise error
            return dt.datetime.strptime(date_string.split("T")[0], '%Y-%m-%d')


        mock_dt_module = mocker.patch('TAT_audit.utils.jira_requests.dt')
        mock_dt_module.datetime.strptime.side_effect = strptime_side_effect

        api_response_input = (
            mock_jira_tickets["single_page_response"] +  # Created 2024-01-30T16:52:18 (IN)
            mock_jira_tickets["multi_page_response_p1"] + # Created 2024-01-30T16:49:38 (IN, MYE - filtered by assay)
            mock_jira_tickets["multi_page_response_p2"]   # Created 2024-01-22T10:00:00 (OUT by date)
        )

        # Only "single_page_response"[0] (CEN) should be included
        expected_dict = {
            "240130_A01303_0329_BH2HWHDRX5": {
                'ticket_key': 'EBH-2377', 'ticket_id': '21865',
                'jira_status': 'All samples released', 'assay_type': 'CEN',
                'date_jira_ticket_created': dt.datetime(2024, 1, 30, 16, 52, 18)
            }
        }
        result = jira_functions_instance.create_jira_info_dict(api_response_input)
        assert result == expected_dict

    def test_create_jira_info_dict_no_assay_field(self, jira_functions_instance, mocker):
        """Test create_jira_info_dict when a ticket is missing the assay custom field."""
        mock_dt_module = mocker.patch('TAT_audit.utils.jira_requests.dt')
        def strptime_side_effect(date_string, date_format): # Allow all dates for this test
            if date_format == '%Y-%m-%d %H:%M:%S':
                return dt.datetime.strptime(date_string.replace('T', ' ').split('.')[0], date_format)
            return dt.datetime.strptime(date_string, date_format)
        mock_dt_module.datetime.strptime.side_effect = strptime_side_effect
        jira_functions_instance.five_days_before_start = "2023-01-01" # Broad range
        jira_functions_instance.five_days_after = "2025-01-01"


        ticket_no_assay = {
            "id": "12345", "key": "NOASSAY-1",
            "fields": {
                "summary": "RUN_NO_ASSAY_FIELD",
                "created": "2024-01-15T10:00:00.000+0000",
                "status": {"name": "Open"},
                "customfield_10070": None # Assay field is None
            }
        }
        ticket_empty_assay_list = {
            "id": "12346", "key": "EMPTYASSAY-1",
            "fields": {
                "summary": "RUN_EMPTY_ASSAY_LIST",
                "created": "2024-01-16T10:00:00.000+0000",
                "status": {"name": "Open"},
                "customfield_10070": [] # Assay field is an empty list
            }
        }
        api_response_input = [ticket_no_assay, ticket_empty_assay_list]

        expected_dict = {
            "RUN_NO_ASSAY_FIELD": {
                'ticket_key': 'NOASSAY-1', 'ticket_id': '12345',
                'jira_status': 'Open', 'assay_type': 'Unknown', # Defaults to 'Unknown'
                'date_jira_ticket_created': dt.datetime(2024, 1, 15, 10, 0, 0)
            },
            "RUN_EMPTY_ASSAY_LIST": {
                'ticket_key': 'EMPTYASSAY-1', 'ticket_id': '12346',
                'jira_status': 'Open', 'assay_type': 'Unknown', # Defaults to 'Unknown'
                'date_jira_ticket_created': dt.datetime(2024, 1, 16, 10, 0, 0)
            }
        }
        # Since "Unknown" is not in jira_functions_instance.assay_types, these will be filtered.
        result = jira_functions_instance.create_jira_info_dict(api_response_input)
        assert result == {}

    @patch('TAT_audit.utils.jira_requests.Levenshtein.distance')
    def test_get_closest_match_in_dict(self, mock_levenshtein_distance, jira_functions_instance):
        """Test finding the closest match for a ticket name in a run dictionary."""
        run_dict = {
            "RUN_EXACT_MATCH": {"assay_type": "CEN"},
            "RUN_ONE_TYPO": {"assay_type": "TSO500"},
            "RUN_THREE_TYPOS": {"assay_type": "MYE"},
            "ANOTHER_RUN": {"assay_type": "TWE"}
        }

        # Scenario 1: Exact match
        def side_effect_exact(s1, s2):
            if s1 == "RUN_EXACT_MATCH" and s2 == "RUN_EXACT_MATCH": return 0
            return 5 # Default high distance for non-exact matches in this scenario
        mock_levenshtein_distance.side_effect = side_effect_exact
        key, typo_info = jira_functions_instance.get_closest_match_in_dict("RUN_EXACT_MATCH", run_dict)
        assert key == "RUN_EXACT_MATCH"
        assert typo_info is None
        # Ensure it checked all keys or broke early on exact match
        # The exact number of calls depends on dict iteration order and if it breaks on dist==0
        # For "RUN_EXACT_MATCH", if it's checked first, it might be 1 call. If last, 4 calls.
        # A robust check is that it was called with the exact match pair.
        mock_levenshtein_distance.assert_any_call("RUN_EXACT_MATCH", "RUN_EXACT_MATCH")


        # Scenario 2: One typo
        def side_effect_one_typo(s1, s2): # s1 is ticket_name_summary ("RUN_ONETYPO")
            if s2 == "RUN_EXACT_MATCH": return 5
            if s2 == "RUN_ONE_TYPO": return 1 # Match
            if s2 == "RUN_THREE_TYPOS": return 5
            if s2 == "ANOTHER_RUN": return 5
            return 10 # Should not happen if all keys covered
        mock_levenshtein_distance.side_effect = side_effect_one_typo
        key, typo_info = jira_functions_instance.get_closest_match_in_dict("RUN_ONETYPO", run_dict) # Ticket name has typo
        assert key == "RUN_ONE_TYPO"
        assert typo_info == {'assay_type': 'TSO500', 'run_name': 'RUN_ONE_TYPO', 'jira_ticket_name': 'RUN_ONETYPO'}

        # Scenario 3: Two typos
        def side_effect_two_typos(s1, s2): # s1 is "RUN_TWOTYPS"
            if s2 == "RUN_EXACT_MATCH": return 5
            if s2 == "RUN_ONE_TYPO": return 2 # Best match
            if s2 == "RUN_THREE_TYPOS": return 5
            if s2 == "ANOTHER_RUN": return 5
            return 10
        mock_levenshtein_distance.side_effect = side_effect_two_typos
        key, typo_info = jira_functions_instance.get_closest_match_in_dict("RUN_TWOTYPS", run_dict)
        assert key == "RUN_ONE_TYPO" # Matched with RUN_ONE_TYPO (dist 2)
        assert typo_info == {'assay_type': 'TSO500', 'run_name': 'RUN_ONE_TYPO', 'jira_ticket_name': 'RUN_TWOTYPS'}

        # Scenario 4: No close match (all > 2 typos)
        mock_levenshtein_distance.side_effect = None # Clear side_effect
        mock_levenshtein_distance.return_value = 3 # All comparisons return 3
        key, typo_info = jira_functions_instance.get_closest_match_in_dict("COMPLETELY_DIFFERENT_RUN", run_dict)
        assert key is None
        assert typo_info is None

        # Scenario 5: Empty run_dict
        mock_levenshtein_distance.reset_mock()
        key, typo_info = jira_functions_instance.get_closest_match_in_dict("ANY_RUN", {})
        assert key is None
        assert typo_info is None
        assert mock_levenshtein_distance.call_count == 0


    @patch('TAT_audit.utils.jira_requests.JiraFunctions.get_closest_match_in_dict')
    @patch('TAT_audit.utils.jira_requests.JiraFunctions.get_ticket_transition_times')
    def test_add_jira_ticket_info(self, mock_get_transitions, mock_get_closest_match, jira_functions_instance, mocker):
        """Test adding Jira ticket information to the main run dictionary."""
        # Configure the jira_functions_instance for this test
        jira_functions_instance.assay_types = ["CEN", "TSO500"] # MYE will be filtered out
        jira_functions_instance.cancelled_statuses = ["Cancelled"]
        jira_functions_instance.open_statuses = ["Open", "On Hold"]
        # Mock dt.datetime.strptime for date comparisons within add_jira_ticket_info
        # The audit_start_obj and audit_end_obj are already MagicMocks from the fixture.
        # We need them to behave correctly for date comparisons.
        # Let audit period be 2024-01-10 to 2024-01-20
        start_obj = dt.datetime(2024, 1, 10)
        end_obj = dt.datetime(2024, 1, 20)
        jira_functions_instance.audit_start_obj = start_obj
        jira_functions_instance.audit_end_obj = end_obj

        run_dict_input = {
            "RUN001_CEN_MATCH": {"assay_type": "CEN"}, # Will be matched
            "RUN003_TSO_ORPHAN": {"assay_type": "TSO500"} # No matching Jira ticket
        }

        # Jira tickets:
        # Ticket 1: Matches RUN001_CEN_MATCH, within audit period, "All samples released"
        # Ticket 2: No 002 project, CEN, within audit period, "All samples released" (becomes runs_no_002_proj)
        # Ticket 3: MYE (filtered out by assay_type), within audit period
        # Ticket 4: CEN, outside audit period (too early)
        # Ticket 5: TSO500, within audit period, "Cancelled" (becomes cancelled_list, no 002 project)
        # Ticket 6: CEN, within audit period, "Open" (becomes open_runs_list, no 002 project)
        # Ticket 7: Matches RUN001_CEN_MATCH (again, to test it updates existing), "Cancelled"
        jira_run_dict_input = {
            "JIRA_RUN001_CEN": { # Matches RUN001_CEN_MATCH
                'ticket_key': 'KEY-1', 'ticket_id': 'ID-1', 'assay_type': 'CEN',
                'jira_status': 'All samples released',
                'date_jira_ticket_created': dt.datetime(2024, 1, 15)
            },
            "JIRA_RUN002_CEN_NO_PROJ": { # No 002 project
                'ticket_key': 'KEY-2', 'ticket_id': 'ID-2', 'assay_type': 'CEN',
                'jira_status': 'All samples released',
                'date_jira_ticket_created': dt.datetime(2024, 1, 16)
            },
            "JIRA_RUN003_MYE": { # Filtered by assay
                'ticket_key': 'KEY-3', 'ticket_id': 'ID-3', 'assay_type': 'MYE',
                'jira_status': 'All samples released',
                'date_jira_ticket_created': dt.datetime(2024, 1, 17)
            },
            "JIRA_RUN004_CEN_EARLY": { # Filtered by date
                'ticket_key': 'KEY-4', 'ticket_id': 'ID-4', 'assay_type': 'CEN',
                'jira_status': 'All samples released',
                'date_jira_ticket_created': dt.datetime(2024, 1, 1)
            },
            "JIRA_RUN005_TSO_CANCELLED": { # Cancelled, no 002
                'ticket_key': 'KEY-5', 'ticket_id': 'ID-5', 'assay_type': 'TSO500',
                'jira_status': 'Cancelled',
                'date_jira_ticket_created': dt.datetime(2024, 1, 12)
            },
            "JIRA_RUN006_CEN_OPEN": { # Open, no 002
                'ticket_key': 'KEY-6', 'ticket_id': 'ID-6', 'assay_type': 'CEN',
                'jira_status': 'Open',
                'date_jira_ticket_created': dt.datetime(2024, 1, 13)
            },
            "JIRA_RUN007_CEN_CANCEL_MATCH": { # Matches RUN001_CEN_MATCH, but is cancelled
                'ticket_key': 'KEY-7', 'ticket_id': 'ID-7', 'assay_type': 'CEN',
                'jira_status': 'Cancelled',
                'date_jira_ticket_created': dt.datetime(2024, 1, 14)
            }
        }

        # Mock behavior of get_closest_match_in_dict
        def closest_match_side_effect(ticket_name, rd):
            if ticket_name == "JIRA_RUN001_CEN": return "RUN001_CEN_MATCH", None
            if ticket_name == "JIRA_RUN007_CEN_CANCEL_MATCH": return "RUN001_CEN_MATCH", {"typo_info": "some_typo"} # Simulate a typo identified
            return None, None # No match for others
        mock_get_closest_match.side_effect = closest_match_side_effect

        # Mock behavior of get_ticket_transition_times (for JIRA_RUN002_CEN_NO_PROJ)
        mock_get_transitions.return_value = {'All samples released': '2024-01-16 12:00:00'}

        # Mock dt.datetime.strptime for the 'All samples released' time string
        mock_strptime_transitions = mocker.patch('TAT_audit.utils.jira_requests.dt.datetime.strptime')
        mock_strptime_transitions.return_value = dt.datetime(2024,1,16,12,0,0)


        expected_run_dict_after = {
            "RUN001_CEN_MATCH": { # Updated by JIRA_RUN001_CEN, then by JIRA_RUN007_CEN_CANCEL_MATCH
                "assay_type": "CEN",
                "jira_status": "Cancelled", # Final status from JIRA_RUN007
                "ticket_key": "KEY-7",
                "ticket_id": "ID-7"
            },
            "RUN003_TSO_ORPHAN": {"assay_type": "TSO500"} # Unchanged
        }
        expected_typo_tickets = [{"typo_info": "some_typo"}]
        expected_runs_no_002_proj = [{
            'run_name': 'JIRA_RUN002_CEN_NO_PROJ', 'assay_type': 'CEN',
            'jira_ticket_created': dt.datetime(2024, 1, 16),
            'jira_ticket_resolved': '2024-01-16 12:00:00',
            'estimated_TAT': 0.5 # Corrected: 12 hours = 0.5 days
        }]
        expected_cancelled_list = [
            { # From JIRA_RUN005_TSO_CANCELLED (no 002 project)
                'run_name': 'JIRA_RUN005_TSO_CANCELLED', 'assay_type': 'TSO500',
                'date_jira_ticket_created': dt.datetime(2024, 1, 12), 'jira_status': 'Cancelled'
            },
            { # From JIRA_RUN007_CEN_CANCEL_MATCH (had a 002 project match)
                'run_name': 'JIRA_RUN007_CEN_CANCEL_MATCH', 'assay_type': 'CEN',
                'date_jira_ticket_created': dt.datetime(2024, 1, 14), 'jira_status': 'Cancelled'
            }
        ]
        expected_open_runs_list = [{
            'run_name': 'JIRA_RUN006_CEN_OPEN', 'assay_type': 'CEN',
            'date_jira_ticket_created': dt.datetime(2024, 1, 13), 'current_status': 'Open'
        }]

        res_run_dict, res_typos, res_no_002, res_cancelled, res_open = \
            jira_functions_instance.add_jira_ticket_info(run_dict_input, jira_run_dict_input)

        assert res_run_dict == expected_run_dict_after
        assert res_typos == expected_typo_tickets
        assert res_no_002 == expected_runs_no_002_proj
        # Order in res_cancelled might vary, so check contents
        assert len(res_cancelled) == len(expected_cancelled_list)
        for item in expected_cancelled_list:
            assert item in res_cancelled
        assert res_open == expected_open_runs_list

        # Check that get_ticket_transition_times was called for JIRA_RUN002_CEN_NO_PROJ
        mock_get_transitions.assert_called_once_with('ID-2')
        # Check strptime for transition time
        mock_strptime_transitions.assert_called_once_with('2024-01-16 12:00:00', '%Y-%m-%d %H:%M:%S')


    @patch('TAT_audit.utils.jira_requests.JiraFunctions.get_ticket_transition_times')
    def test_add_transition_times(self, mock_get_transitions, jira_functions_instance):
        """Test adding Jira ticket transition times to the run dictionary."""
        run_dict_input = {
            "RUN001_HAS_TICKET_ID": {"ticket_id": "ID_001"},
            "RUN002_NO_TICKET_ID": {},
            "RUN003_HAS_TICKET_ID_RESOLVED": {"ticket_id": "ID_003", "jira_status": "All samples released"}
        }

        # Mock return values for get_ticket_transition_times
        transitions1 = {"Open": "2023-01-01 10:00:00", "In Progress": "2023-01-01 11:00:00"}
        transitions3 = {"Open": "2023-01-02 09:00:00", "All samples released": "2023-01-02 15:00:00"}
        mock_get_transitions.side_effect = [transitions1, transitions3]

        expected_run_dict = {
            "RUN001_HAS_TICKET_ID": {
                "ticket_id": "ID_001",
                "change_log": transitions1
            },
            "RUN002_NO_TICKET_ID": {}, # Unchanged
            "RUN003_HAS_TICKET_ID_RESOLVED": {
                "ticket_id": "ID_003",
                "jira_status": "All samples released",
                "change_log": transitions3,
                "jira_resolved": "2023-01-02 15:00:00" # Added because "All samples released" is in changelog
            }
        }

        result_dict = jira_functions_instance.add_transition_times(run_dict_input)

        assert result_dict == expected_run_dict
        calls_get_transitions = [call("ID_001"), call("ID_003")]
        mock_get_transitions.assert_has_calls(calls_get_transitions)
        assert mock_get_transitions.call_count == 2
    # End of TestJiraFunctions class
