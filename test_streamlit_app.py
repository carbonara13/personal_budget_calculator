import pandas as pd
import pytest
import streamlit as st

from streamlit_app import (
    MONTH_NAMES,
    build_export_csv,
    build_quarterly_expenses_df,
    build_quarterly_summary_df,
    calculate_month_budget,
    init_session_state,
    save_month_result,
)


@pytest.fixture(autouse=True)
def clear_session_state():
    """Очищує session_state перед кожним тестом."""
    st.session_state.clear()
    yield
    st.session_state.clear()


def test_init_session_state_creates_monthly_results():
    init_session_state()

    assert "monthly_results" in st.session_state
    assert isinstance(st.session_state.monthly_results, dict)
    assert list(st.session_state.monthly_results.keys()) == MONTH_NAMES
    assert all(value is None for value in st.session_state.monthly_results.values())


def test_calculate_month_budget_surplus():
    expenses = {
        "Їжа": 3000.0,
        "Транспорт": 1000.0,
        "Розваги": 500.0,
        "Житло / Комунальні": 4000.0,
        "Інше": 500.0,
    }

    df, total_expenses, balance, status = calculate_month_budget(12000.0, expenses)

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["Категорія", "Сума"]
    assert total_expenses == 9000.0
    assert balance == 3000.0
    assert status == "Профіцитний бюджет ✅"


def test_calculate_month_budget_balanced():
    expenses = {
        "Їжа": 2000.0,
        "Транспорт": 1000.0,
        "Розваги": 500.0,
        "Житло / Комунальні": 3500.0,
        "Інше": 0.0,
    }

    _, total_expenses, balance, status = calculate_month_budget(7000.0, expenses)

    assert total_expenses == 7000.0
    assert balance == 0.0
    assert status == "Збалансований бюджет ⚖️"


def test_calculate_month_budget_deficit():
    expenses = {
        "Їжа": 2500.0,
        "Транспорт": 1000.0,
        "Розваги": 1000.0,
        "Житло / Комунальні": 4000.0,
        "Інше": 1000.0,
    }

    _, total_expenses, balance, status = calculate_month_budget(8000.0, expenses)

    assert total_expenses == 9500.0
    assert balance == -1500.0
    assert status == "Дефіцитний бюджет ⚠️"


def test_save_month_result_stores_data_in_session_state():
    init_session_state()

    expenses = {
        "Їжа": 1000.0,
        "Транспорт": 500.0,
        "Розваги": 300.0,
        "Житло / Комунальні": 2000.0,
        "Інше": 200.0,
    }

    df, total_expenses, balance, status = calculate_month_budget(6000.0, expenses)
    save_month_result("Місяць 1", 6000.0, df, total_expenses, balance, status)

    saved = st.session_state.monthly_results["Місяць 1"]

    assert saved is not None
    assert saved["income"] == 6000.0
    assert saved["total_expenses"] == 4000.0
    assert saved["balance"] == 2000.0
    assert saved["status"] == "Профіцитний бюджет ✅"
    assert "Місяць" in saved["expenses_df"].columns
    assert all(saved["expenses_df"]["Місяць"] == "Місяць 1")


def test_build_quarterly_expenses_df_combines_all_months():
    init_session_state()

    month_data = [
        ("Місяць 1", 10000.0, {"Їжа": 1000.0, "Транспорт": 500.0, "Розваги": 300.0, "Житло / Комунальні": 3000.0, "Інше": 200.0}),
        ("Місяць 2", 11000.0, {"Їжа": 1200.0, "Транспорт": 600.0, "Розваги": 400.0, "Житло / Комунальні": 3200.0, "Інше": 300.0}),
        ("Місяць 3", 9000.0, {"Їжа": 900.0, "Транспорт": 400.0, "Розваги": 200.0, "Житло / Комунальні": 2800.0, "Інше": 100.0}),
    ]

    for month_name, income, expenses in month_data:
        df, total_expenses, balance, status = calculate_month_budget(income, expenses)
        save_month_result(month_name, income, df, total_expenses, balance, status)

    combined_df = build_quarterly_expenses_df()

    assert isinstance(combined_df, pd.DataFrame)
    assert list(combined_df.columns) == ["Місяць", "Категорія", "Сума"]
    assert len(combined_df) == 15
    assert set(combined_df["Місяць"]) == {"Місяць 1", "Місяць 2", "Місяць 3"}


def test_build_quarterly_expenses_df_returns_empty_dataframe_when_no_data():
    init_session_state()

    combined_df = build_quarterly_expenses_df()

    assert isinstance(combined_df, pd.DataFrame)
    assert list(combined_df.columns) == ["Місяць", "Категорія", "Сума"]
    assert combined_df.empty


def test_build_quarterly_summary_df_groups_by_category():
    combined_df = pd.DataFrame(
        [
            {"Місяць": "Місяць 1", "Категорія": "Їжа", "Сума": 1000.0},
            {"Місяць": "Місяць 1", "Категорія": "Транспорт", "Сума": 500.0},
            {"Місяць": "Місяць 2", "Категорія": "Їжа", "Сума": 1200.0},
            {"Місяць": "Місяць 2", "Категорія": "Транспорт", "Сума": 700.0},
            {"Місяць": "Місяць 3", "Категорія": "Їжа", "Сума": 800.0},
        ]
    )

    summary_df = build_quarterly_summary_df(combined_df)

    assert isinstance(summary_df, pd.DataFrame)
    assert list(summary_df.columns) == ["Категорія", "Сума"]

    summary = dict(zip(summary_df["Категорія"], summary_df["Сума"]))
    assert summary["Їжа"] == 3000.0
    assert summary["Транспорт"] == 1200.0


def test_build_quarterly_summary_df_returns_empty_for_empty_input():
    empty_df = pd.DataFrame(columns=["Місяць", "Категорія", "Сума"])

    summary_df = build_quarterly_summary_df(empty_df)

    assert isinstance(summary_df, pd.DataFrame)
    assert list(summary_df.columns) == ["Категорія", "Сума"]
    assert summary_df.empty


def test_build_export_csv_contains_month_rows_and_totals():
    init_session_state()

    month_data = [
        ("Місяць 1", 10000.0, {"Їжа": 1000.0, "Транспорт": 500.0, "Розваги": 300.0, "Житло / Комунальні": 3000.0, "Інше": 200.0}),
        ("Місяць 2", 11000.0, {"Їжа": 1200.0, "Транспорт": 600.0, "Розваги": 400.0, "Житло / Комунальні": 3200.0, "Інше": 300.0}),
        ("Місяць 3", 9000.0, {"Їжа": 900.0, "Транспорт": 400.0, "Розваги": 200.0, "Житло / Комунальні": 2800.0, "Інше": 100.0}),
    ]

    expected_total_income = 0.0
    expected_total_expenses = 0.0
    expected_total_balance = 0.0

    for month_name, income, expenses in month_data:
        df, total_expenses, balance, status = calculate_month_budget(income, expenses)
        save_month_result(month_name, income, df, total_expenses, balance, status)

        expected_total_income += income
        expected_total_expenses += total_expenses
        expected_total_balance += balance

    csv_bytes = build_export_csv()
    csv_text = csv_bytes.decode("utf-8-sig")
    export_df = pd.read_csv(pd.io.common.StringIO(csv_text))

    assert list(export_df.columns) == ["Місяць", "Категорія", "Сума"]

    totals_df = export_df[export_df["Місяць"] == "ВСЬОГО"]
    totals = dict(zip(totals_df["Категорія"], totals_df["Сума"]))

    assert totals["ДОХІД"] == expected_total_income
    assert totals["ВИТРАТИ"] == expected_total_expenses
    assert totals["БАЛАНС"] == expected_total_balance


def test_build_export_csv_contains_expected_number_of_rows():
    init_session_state()

    for month_name in MONTH_NAMES:
        expenses = {
            "Їжа": 1000.0,
            "Транспорт": 500.0,
            "Розваги": 300.0,
            "Житло / Комунальні": 2000.0,
            "Інше": 200.0,
        }
        df, total_expenses, balance, status = calculate_month_budget(7000.0, expenses)
        save_month_result(month_name, 7000.0, df, total_expenses, balance, status)

    csv_bytes = build_export_csv()
    csv_text = csv_bytes.decode("utf-8-sig")
    export_df = pd.read_csv(pd.io.common.StringIO(csv_text))

    # 3 місяці * 5 категорій + 3 підсумкові рядки
    assert len(export_df) == 18
