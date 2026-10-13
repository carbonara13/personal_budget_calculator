import io
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Калькулятор особистого бюджету — квартальний звіт",
    page_icon="📊",
    layout="wide",
)

CATEGORIES = [
    "Їжа",
    "Транспорт",
    "Розваги",
    "Житло / Комунальні",
    "Інше",
]

MONTH_NAMES = ["Місяць 1", "Місяць 2", "Місяць 3"]


def init_session_state() -> None:
    """Ініціалізує стан застосунку."""
    st.session_state.setdefault("monthly_drafts", {
        month: {"income": 0.0, **dict.fromkeys(CATEGORIES, 0.0)} for month in MONTH_NAMES
    })
    if "monthly_results" not in st.session_state:
        st.session_state.monthly_results = {
            month: None for month in MONTH_NAMES
        }


def calculate_month_budget(income: float, expenses: dict) -> tuple[pd.DataFrame, float, float, str]:
    """
    Розраховує бюджет за місяць.

    Returns:
        df: DataFrame з витратами
        total_expenses: загальна сума витрат
        balance: залишок коштів
        status: статус бюджету
    """
    values = [float(income), *(float(v) for v in expenses.values())]
    if any(value < 0 for value in values):
        raise ValueError("Дохід і витрати мають бути невід’ємними числами.")
    df = pd.DataFrame({"Категорія": list(expenses), "Сума": list(expenses.values())})
    total_expenses = round(sum(values[1:]), 2)
    balance = round(values[0] - total_expenses, 2)
    status = (
        "Профіцитний бюджет ✅" if balance > 0 else
        "Дефіцитний бюджет ⚠️" if balance < 0 else
        "Збалансований бюджет ⚖️"
    )
    return df, total_expenses, balance, status


def save_month_result(
    month_name: str,
    income: float,
    df: pd.DataFrame,
    total_expenses: float,
    balance: float,
    status: str,
) -> None:
    """Зберігає результат місяця в session_state."""
    month_df = df.copy()
    month_df["Місяць"] = month_name

    st.session_state.monthly_results[month_name] = {
        "income": income,
        "expenses_df": month_df,
        "total_expenses": total_expenses,
        "balance": balance,
        "status": status,
    }


def render_month_tab(month_name: str) -> None:
    """Відображає вкладку одного місяця; чернетки переживають навігацію."""
    draft = st.session_state.monthly_drafts[month_name]

    def remember_input(field: str, key: str) -> None:
        draft[field] = st.session_state[key]

    def number(field: str, label: str) -> float:
        key = f"{month_name}_{field}"
        st.session_state.setdefault(key, draft[field])
        return st.number_input(
            label, min_value=0.0, step=100.0, format="%.2f", key=key,
            on_change=remember_input, args=(field, key),
        )

    income = number("income", "Дохід, грн")
    st.subheader("Витрати, грн")
    expenses = {category: number(category, category) for category in CATEGORIES}
    if st.button("Розрахувати", key=f"calculate_{month_name}", type="primary"):
        df, total, balance, status = calculate_month_budget(income, expenses)
        save_month_result(month_name, income, df, total, balance, status)
        st.rerun()

    result = st.session_state.monthly_results[month_name]
    if result is None:
        st.info("Введіть дані та натисніть «Розрахувати», щоб зберегти місяць у звіті.")
        return
    saved_expenses = dict(zip(result["expenses_df"]["Категорія"], result["expenses_df"]["Сума"]))
    if income != result["income"] or expenses != saved_expenses:
        st.warning("Дані змінено. Натисніть «Розрахувати», щоб оновити збережений результат.")
    render_indicators(result["income"], result["total_expenses"], result["balance"])
    show_status(result["balance"], result["status"])
    display_expenses(result["expenses_df"][["Категорія", "Сума"]])


def build_quarterly_expenses_df() -> pd.DataFrame:
    """Об'єднує витрати за всі місяці в один DataFrame."""
    frames = [result["expenses_df"] for result in st.session_state.monthly_results.values()
              if result is not None]
    columns = ["Місяць", "Категорія", "Сума"]
    if not frames:
        return pd.DataFrame(columns=columns)
    combined_df = pd.concat(frames, ignore_index=True)
    return combined_df[columns]


def build_quarterly_summary_df(combined_df: pd.DataFrame) -> pd.DataFrame:
    """Створює зведення витрат по категоріях."""
    return combined_df.groupby("Категорія", as_index=False, sort=False)["Сума"].sum().round({"Сума": 2})


def build_export_csv() -> bytes:
    """Формує CSV-файл квартального звіту."""
    combined = build_quarterly_expenses_df()
    export = combined
    income, expenses, balance = quarterly_totals()
    totals = pd.DataFrame({"Місяць": ["ВСЬОГО"] * 3,
                           "Категорія": ["ДОХІД", "ВИТРАТИ", "БАЛАНС"],
                           "Сума": [income, expenses, balance]})
    csv_buffer = io.StringIO()
    pd.concat([export, totals], ignore_index=True).to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue().encode("utf-8-sig")


def render_quarter_report() -> None:
    """Відображає попередній або повний квартальний звіт."""
    st.header("Квартальний звіт")
    missing = [month for month, result in st.session_state.monthly_results.items() if result is None]
    if len(missing) == len(MONTH_NAMES):
        st.info("Ще немає розрахунків. Заповніть місячні дані та натисніть «Розрахувати».")
        return
    if missing:
        st.warning("Неповний квартал. Немає розрахунків: " + ", ".join(missing)
                   + ". Нижче наведено підсумки лише збережених місяців.")
    st.caption("Звіт використовує останні збережені розрахунки. Після редагування місяця натисніть «Розрахувати».")
    income, expenses, balance = quarterly_totals()
    render_indicators(income, expenses, balance)
    show_status(balance)
    display_expenses(build_quarterly_summary_df(build_quarterly_expenses_df()))
    st.download_button(
        "📥 Завантажити квартальний звіт", data=build_export_csv(),
        file_name="quarterly_budget.csv", mime="text/csv", disabled=bool(missing),
    )
    if missing:
        st.caption("CSV стане доступним після розрахунку всіх трьох місяців.")


def quarterly_totals() -> tuple[float, float, float]:
    results = [r for r in st.session_state.monthly_results.values() if r is not None]
    income = round(sum(float(r["income"]) for r in results), 2)
    expenses = round(sum(float(r["total_expenses"]) for r in results), 2)
    return income, expenses, round(income - expenses, 2)


def render_indicators(income: float, expenses: float, balance: float) -> None:
    for column, label, value in zip(st.columns(3), ["Дохід", "Витрати", "Баланс"], [income, expenses, balance]):
        column.metric(label, f"{value:,.2f} грн")


def show_status(balance: float, status: str | None = None) -> None:
    message = status or ("Профіцитний бюджет ✅" if balance > 0 else
                         "Дефіцитний бюджет ⚠️" if balance < 0 else "Збалансований бюджет ⚖️")
    if balance < 0:
        st.error(message)
    elif balance > 0:
        st.success(message)
    else:
        st.info(message)


def display_expenses(df: pd.DataFrame) -> None:
    st.dataframe(df, hide_index=True, width="stretch")
    st.bar_chart(df, x="Категорія", y="Сума", x_label="Категорія", y_label="Витрати, грн")



def main() -> None:
    init_session_state()

    st.title("💰 Калькулятор особистого бюджету — рівень 2")
    st.write(
        "Додаток дозволяє вести бюджет за 3 місяці та формувати зведений квартальний звіт."
    )

    section = st.sidebar.radio(
        "Навігація",
        ["Місячні дані", "Квартальний звіт"],
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Стан заповнення")
    for month_name in MONTH_NAMES:
        if st.session_state.monthly_results.get(month_name) is not None:
            st.sidebar.success(f"{month_name}: готово")
        else:
            st.sidebar.info(f"{month_name}: немає розрахунку")

    if section == "Місячні дані":
        st.header("📅 Дані по місяцях")
        tabs = st.tabs(MONTH_NAMES)

        for tab, month_name in zip(tabs, MONTH_NAMES):
            with tab:
                render_month_tab(month_name)

    elif section == "Квартальний звіт":
        render_quarter_report()


if __name__ == "__main__":
    main()
