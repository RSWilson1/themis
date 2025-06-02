import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, call
import plotly.graph_objects as go
import plotly.express as px 

from TAT_audit.utils.plotting import PlottingFunctions

@pytest.fixture
def plotting_functions_instance():
    return PlottingFunctions(
        cancelled_statuses=["Cancelled", "Data not received"],
        audit_start="2023-01-01",
        audit_end="2023-01-31",
        tat_standard=7,
        font_size=10
    )

@pytest.fixture
def sample_assay_df():
    # Create a sample DataFrame that mimics the structure expected by plotting functions
    data = {
        'ticket_hyperlink': ['<a href="...">RUN001</a>', '<a href="...">RUN002</a>', '<a href="...">RUN003_CANCELLED</a>'],
        'run_name': ['RUN001', 'RUN002', 'RUN003_CANCELLED'],
        'upload_to_first_job': [1.0, 1.5, 0.5],
        'processing_time': [3.0, 2.5, 1.0],
        'processing_end_to_release': [2.0, 1.0, None], # RUN003 might not be released
        'upload_to_release': [6.0, 5.0, None],
        'urgents_time': [None, None, None],
        'on_hold_time': [None, None, None],
        'jira_status': ['All samples released', 'All samples released', 'Cancelled'],
        'week_start': ['02-01-23', '02-01-23', '09-01-23'] # dd-mm-yy
    }
    df = pd.DataFrame(data)
    # Ensure correct dtypes for any calculations if necessary, though plotting might be tolerant
    return df

@pytest.fixture
def sample_assay_df_with_open_runs():
    data = {
        'ticket_hyperlink': ['<a href="...">RUN004_URGENT</a>', '<a href="...">RUN005_ONHOLD</a>'],
        'run_name': ['RUN004_URGENT', 'RUN005_ONHOLD'],
        'upload_to_first_job': [0.5, 0.8],
        'processing_time': [2.0, 1.5],
        'processing_end_to_release': [None, None],
        'upload_to_release': [None, None],
        'urgents_time': [1.2, None], # Urgent run has urgents_time
        'on_hold_time': [None, 0.8], # On hold run has on_hold_time
        'jira_status': ['Urgent samples released', 'On hold'],
        'week_start': ['16-01-23', '16-01-23']
    }
    return pd.DataFrame(data)


class TestPlottingFunctions:

    def test_init(self):
        cancelled_statuses = ["StatusA"]
        audit_start = "2022-01-01"
        audit_end = "2022-01-31"
        tat_standard = 5
        font_size = 12
        
        pf = PlottingFunctions(cancelled_statuses, audit_start, audit_end, tat_standard, font_size)
        
        assert pf.cancelled_statuses == cancelled_statuses
        assert pf.audit_start == audit_start
        assert pf.audit_end == audit_end
        assert pf.tat_standard == tat_standard
        assert pf.font_size == font_size

    @patch('TAT_audit.utils.plotting.make_subplots')
    @patch('TAT_audit.utils.plotting.go.Bar')
    @patch('pandas.period_range') # To control the weeks generated
    def test_create_tat_fig_split_by_week(self, mock_period_range, mock_go_bar, mock_make_subplots, plotting_functions_instance, sample_assay_df):
        """Test creation of the Turnaround Time (TAT) figure split by week."""
        # Mock make_subplots to return a MagicMock for the figure object
        mock_fig = MagicMock(spec=go.Figure)
        mock_make_subplots.return_value = mock_fig
        
        # Mock pandas.period_range to return a fixed set of periods (weeks)
        # This controls the number of subplots and their titles
        mock_periods = [
            MagicMock(start_time=pd.Timestamp('2023-01-02')), # Corresponds to week '02-01-23'
            MagicMock(start_time=pd.Timestamp('2023-01-09'))  # Corresponds to week '09-01-23'
        ]
        mock_period_range.return_value = mock_periods
        
        assay_type = "CEN"
        html_output = plotting_functions_instance.create_tat_fig_split_by_week(sample_assay_df, assay_type)
        
        # Verify make_subplots was called correctly
        # Based on mock_periods, we expect 2 columns (weeks)
        # The norm_widths will be calculated based on runs per week in sample_assay_df
        # Week '02-01-23': 2 runs (RUN001, RUN002 - RUN003 is cancelled and filtered out before this)
        # Week '09-01-23': 0 runs (RUN003 is cancelled)
        # So, run_totals will be [2, 1] (1 for empty week) -> norm_widths [2/3, 1/3]
        
        # Filter out cancelled runs as done in the actual function
        df_for_plot = sample_assay_df[~sample_assay_df.jira_status.isin(plotting_functions_instance.cancelled_statuses)]
        
        # Calculate expected run_totals and norm_widths
        date_weeks_expected = ['02-01-23', '09-01-23'] # from mock_periods
        
        # Run totals: df_for_plot has 2 runs in '02-01-23', 0 in '09-01-23'
        # The code sets df_len = 1 if 0, so run_totals = [2, 1]
        # norm_widths = [2/(2+1), 1/(2+1)] = [0.666..., 0.333...]
        
        mock_make_subplots.assert_called_once()
        args, kwargs = mock_make_subplots.call_args
        assert kwargs['rows'] == 1
        assert kwargs['cols'] == len(date_weeks_expected)
        assert kwargs['shared_yaxes'] is True
        assert kwargs['subplot_titles'] == [f"w/c<br>{str(week)}" for week in date_weeks_expected]
        # Check column_widths (approximate due to float precision)
        assert len(kwargs['column_widths']) == 2
        assert pytest.approx(kwargs['column_widths'][0]) == 2/3
        assert pytest.approx(kwargs['column_widths'][1]) == 1/3
        
        # Verify go.Bar calls for the first week (RUN001, RUN002)
        # 3 bars per run for 'upload_to_first_job', 'processing_time', 'processing_end_to_release'
        # Total 3 * 2 = 6 go.Bar calls for the first week
        # The second week is empty, so it makes one dummy go.Bar call and updates xaxes.
        
        # Check that append_trace was called on the mock_fig
        # RUN001 and RUN002 are in the first week. RUN003 is cancelled.
        # 3 traces for RUN001, 3 for RUN002.
        # The empty week (09-01-23) will also attempt to append one trace (which is mocked by go.Bar)
        # So, 2 * 3 + 1 = 7 calls to append_trace
        assert mock_fig.append_trace.call_count == 7 
        
        # Check some parameters of go.Bar calls for the first run (RUN001) in the first week
        # These calls are made via fig.append_trace(go.Bar(...), row=1, col=1)
        # We can check the arguments passed to go.Bar constructor
        
        # Get calls to go.Bar
        bar_calls = mock_go_bar.call_args_list
        assert len(bar_calls) == 7 # 6 for data, 1 for empty week placeholder

        # Example check for the first bar of RUN001
        call1_kwargs = bar_calls[0].kwargs
        assert list(call1_kwargs['x']) == ['<a href="...">RUN001</a>', '<a href="...">RUN002</a>'] # From df_for_plot for week '02-01-23'
        assert list(call1_kwargs['y']) == [1.0, 1.5] # upload_to_first_job for RUN001 and RUN002
        assert call1_kwargs['name'] == 'Upload to processing start'
        
        # Verify other figure update calls
        mock_fig.add_hline.assert_called_once_with(y=plotting_functions_instance.tat_standard, line_dash="dash")
        mock_fig.update_xaxes.assert_any_call(tickangle=45, categoryorder='category ascending')
        mock_fig.update_layout.assert_called_once()
        mock_fig.update_traces.assert_called() # Called for each trace group
        mock_fig.for_each_trace.assert_called_once() # For legend deduplication
        mock_fig.update_annotations.assert_called_once_with(font_size=plotting_functions_instance.font_size)
        mock_fig.add_annotation.assert_called_once() # For x-axis title

        # Verify HTML output
        mock_fig.to_html.assert_called_once_with(full_html=False, include_plotlyjs=False)
        assert html_output == mock_fig.to_html.return_value

    @patch('TAT_audit.utils.plotting.make_subplots')
    @patch('TAT_audit.utils.plotting.go.Bar')
    @patch('pandas.period_range')
    def test_create_tat_fig_with_open_runs(self, mock_period_range, mock_go_bar, mock_make_subplots, plotting_functions_instance, sample_assay_df_with_open_runs):
        """Test create_tat_fig_split_by_week with runs that are 'Urgent samples released' or 'On hold'."""
        mock_fig = MagicMock(spec=go.Figure)
        mock_make_subplots.return_value = mock_fig
        mock_periods = [MagicMock(start_time=pd.Timestamp('2023-01-16'))] # One week '16-01-23'
        mock_period_range.return_value = mock_periods

        assay_type = "TSO500"
        plotting_functions_instance.create_tat_fig_split_by_week(sample_assay_df_with_open_runs, assay_type)

        # Expected traces:
        # RUN004_URGENT: upload_to_first_job, processing_time, urgents_time (3 traces)
        # RUN005_ONHOLD: upload_to_first_job, processing_time, on_hold_time (3 traces)
        # Total = 3 + 3 = 6 traces
        assert mock_fig.append_trace.call_count == 6
        
        bar_calls_kwargs = [c.kwargs for c in mock_go_bar.call_args_list]

        # Check for 'Urgent samples released' bar
        urgent_bar_found = any(
            bar_kw.get('name') == 'Pipeline end to now - urgent samples released' and \
            list(bar_kw.get('y', [])) == [1.2, None] # RUN004 has 1.2, RUN005 has None for urgents_time
            for bar_kw in bar_calls_kwargs
        )
        assert urgent_bar_found, "Bar for 'Urgent samples released' not found or incorrect"

        # Check for 'On hold' bar
        on_hold_bar_found = any(
            bar_kw.get('name') == 'Last processing step to now - On hold' and \
            list(bar_kw.get('y', [])) == [None, 0.8] # RUN004 has None, RUN005 has 0.8 for on_hold_time
            for bar_kw in bar_calls_kwargs
        )
        assert on_hold_bar_found, "Bar for 'On hold' not found or incorrect"

    @patch('TAT_audit.utils.plotting.px.scatter')
    def test_create_upload_day_fig(self, mock_px_scatter, plotting_functions_instance, sample_assay_df):
        """Test creation of the upload day vs. TAT figure."""
        mock_fig = MagicMock(spec=go.Figure)
        mock_px_scatter.return_value = mock_fig
        
        # Ensure 'upload_time' column is datetime for .dt.day_name() to work
        df_for_plot = sample_assay_df.copy()
        # Create dummy datetime objects for 'upload_time'
        # These specific dates will result in Monday, Tuesday, Wednesday if they were real
        df_for_plot['upload_time'] = pd.to_datetime(['2023-01-02', '2023-01-03', '2023-01-04'])


        assay_type = "CEN"
        html_output = plotting_functions_instance.create_upload_day_fig(df_for_plot, assay_type)
        
        # Verify px.scatter was called
        mock_px_scatter.assert_called_once()
        args, kwargs = mock_px_scatter.call_args
        
        pd.testing.assert_frame_equal(kwargs['data_frame'], df_for_plot)
        assert kwargs['x'] == 'upload_day'
        assert kwargs['y'] == 'upload_to_release'
        assert kwargs['custom_data'] == ['run_name']
        # Color is a pandas Series, check its name or values if possible, or that it was passed
        assert isinstance(kwargs['color'], pd.Series)
        assert kwargs['color_discrete_map'] == {True: "green", False: "red"}
        
        # Verify figure updates
        mock_fig.update_xaxes.assert_called_once()
        mock_fig.update_layout.assert_called_once()
        mock_fig.update_traces.assert_called_once()
        
        # Verify HTML output
        mock_fig.to_html.assert_called_once_with(full_html=False, include_plotlyjs=False)
        assert html_output == mock_fig.to_html.return_value

    @patch('TAT_audit.utils.plotting.go.Figure')
    def test_create_upload_day_fig_empty_or_no_relevant_data(self, mock_go_figure_constructor, plotting_functions_instance):
        """Test create_upload_day_fig with empty df or no 'upload_to_release' data."""
        mock_fig_instance = MagicMock(spec=go.Figure)
        mock_go_figure_constructor.return_value = mock_fig_instance
        
        assay_type = "TSO500"
        
        # Scenario 1: Empty DataFrame
        empty_df = pd.DataFrame(columns=sample_assay_df().columns)
        html_output_empty = plotting_functions_instance.create_upload_day_fig(empty_df, assay_type)
        
        mock_go_figure_constructor.assert_called_once() # Called to create the empty figure
        mock_fig_instance.update_layout.assert_called_once() # Called to add "No data" annotation
        assert html_output_empty == mock_fig_instance.to_html.return_value
        
        mock_go_figure_constructor.reset_mock()
        mock_fig_instance.reset_mock()

        # Scenario 2: DataFrame with no 'upload_to_release' values (all NaN)
        df_no_release = sample_assay_df().copy()
        df_no_release['upload_to_release'] = None 
        df_no_release['upload_time'] = pd.to_datetime(['2023-01-02', '2023-01-03', '2023-01-04'])

        html_output_no_release = plotting_functions_instance.create_upload_day_fig(df_no_release, assay_type)
        
        mock_go_figure_constructor.assert_called_once()
        mock_fig_instance.update_layout.assert_called_once()
        assert html_output_no_release == mock_fig_instance.to_html.return_value


    @patch.object(PlottingFunctions, 'create_tat_fig_split_by_week', return_value="<html_tat_fig/>")
    @patch.object(PlottingFunctions, 'create_upload_day_fig', return_value="<html_upload_fig/>")
    def test_create_both_figures(self, mock_create_upload_fig, mock_create_tat_fig, plotting_functions_instance, sample_assay_df):
        """Test creation of both TAT and upload day figures."""
        assay_df_input = sample_assay_df.copy()
        assay_type_input = "MYE"
        
        tat_fig_html, upload_fig_html = plotting_functions_instance.create_both_figures(assay_df_input, assay_type_input)
        
        mock_create_tat_fig.assert_called_once_with(assay_df_input, assay_type_input)
        mock_create_upload_fig.assert_called_once_with(assay_df_input, assay_type_input)
        
        assert tat_fig_html == "<html_tat_fig/>"
        assert upload_fig_html == "<html_upload_fig/>"

    # End of TestPlottingFunctions class
