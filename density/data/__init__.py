from bokeh.plotting import figure
from pandas import PeriodIndex

import pandas as pd

PANTONE_292 = (105, 179, 231)


def db_to_pandas(conn):
    """ Return occupancy data as pandas dataframe

    column dtypes:
        group_id: int64
        group_name: category
        parent_id: int64
        parent_name: category
        client_count: int64
    index: DateTimeIndex -- dump_time

    Parameters
    ----------
    conn: psycopg2.extensions.connection
        Connection to db
    Returns
    -------
    pandas.DataFrame
        Density data in a Dataframe
    """

    df = pd.read_sql('SELECT * FROM density_data', conn) \
           .set_index("dump_time") \
           .assign(group_name=lambda df: df["group_name"].astype('category'),
                   parent_name=lambda df: df["parent_name"].astype('category'))

    return df


def plot_prediction_point_estimate(conn, series, predictor):
    """ Returns bokeh plot of current + predicted capacity

    Returns a figure with 2 lines, one for past capacity and another for
    future predicted capacity using predictor function. The plot
    displays 24 hours into the future at 15 minute intervals.

    Parameters
    ----------
    conn: psycopg2.extensions.connection
        Connection to db
    series: pandas.Series
        A series of a single floor's occupancy. Its index are past times
        and its values are the observec occupancies, and its name is the
        floor name.
    predictor: Callable[[psycopg2.extensions.connection, str, pd.PeriodIndex],
                         pd.Series]
        Takes the room name and a PeriodIndex of times of future times
        and returns the predicted occupancy of the room at those times

    Returns
    -------
    bokeh.plotting.figure.Figure
    """
    future_dts = PeriodIndex(start=series.index[-1], freq='15T',
                             periods=24 * 4)
    predictions = pd.Series(predictor(conn, series.name, future_dts),
                            index=future_dts.to_datetime())

    p = figure(x_axis_type="datetime")
    p.line(series.index, series, color="dodgerblue", line_width=3,
           line_cap="round")
    p.line(predictions.index, predictions, color="crimson", line_width=3,
           line_dash="dashed", line_cap="round")

    p.xaxis.axis_label = "Time of Day"
    p.xaxis.axis_line_width = 3
    p.xaxis.axis_line_color = PANTONE_292
    p.xaxis.major_label_text_color = PANTONE_292

    p.yaxis.axis_label = "Capacity"
    p.yaxis.axis_line_color = PANTONE_292
    p.yaxis.major_label_text_color = PANTONE_292
    p.yaxis.major_label_orientation = "vertical"
    p.yaxis.axis_line_width = 3

    return p


def df_predict(conn, index, floor):
    """ Return series of predicted capacities for a provided set of times

    Parameters
    ----------
    conn: psycopg2.extensions.connection
        Connection to db
    index: pd.DatetimeIndex/pd.PeriodIndex
        Index of all times for querying predictions.
    floor: str
        Floor to obtain predictions for.

    Returns
    -------
    pd.Series
        Series consisting of predictions for each time in the index.
    """
    df = db_to_pandas(conn)
    means = get_historical_means(df, floor, index)
    predictions = pd.Series(means, index=index)

    return predictions


def get_historical_means(df, floor, index):
    """ Return mean capacities for a floor at the same day of week and time

    Parameters
    ----------
    df: pd.Dataframe
        Dataframe consisting of Density data.
    floor: str
        Floor to obtain predictions for.
    index: pd.DatetimeIndex/pd.PeriodIndex
        Index of dates to obtain history for

    Returns
    -------
    List[float]
        List of historical averages
    """
    groups = df.groupby([df.group_name, df.index.dayofweek, df.index.time])
    return [groups
            .get_group((floor, date.dayofweek, date.time()))['client_count']
            .mean()
            for date in index]
