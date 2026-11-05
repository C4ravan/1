import streamlit as st
import pandas as pd


# =====================================================================
# [Module A] DataProcessor: 데이터 파싱 및 정제 클래스 (담당자 1)
# =====================================================================
class DataProcessor:
    """
    업로드된 교과목 Excel/CSV 파일을 읽어오고,
    문자열 시간표(3개 교시)와 담당교수 정보를 결합하여
    총 4개의 고유 숫자 리스트(예: [11, 12, 31, 101])로 변환하는 클래스입니다.
    """

    def __init__(self):
        # 요일을 숫자의 '십의 자리'로 바꾸기 위한 딕셔너리 (11 ~ 59 사이의 2자리 숫자)
        self.day_map = {"월": 10, "화": 20, "수": 30, "목": 40, "금": 50}
        # 반대로 숫자를 다시 한글(예: 11 -> '월1교시')로 바꿀 때 사용할 딕셔너리
        self.reverse_day_map = {1: "월", 2: "화", 3: "수", 4: "목", 5: "금"}
        # 교수님 성함을 101번부터 시작하는 3자리 고유 숫자로 매핑할 딕셔너리
        self.prof_map = {}

    def load_data(self, uploaded_file):
        """
        코드 내부에 샘플 과목을 직접 적지 않고,
        사용자가 업로드한 Excel(.xlsx) 또는 CSV(.csv) 파일만 읽어옵니다.
        """
        if uploaded_file is None:
            return None

        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        return df

    def build_professor_map(self, df):
        """
        데이터프레임에 등장하는 교수님들에게 101번부터 순서대로 고유 번호를 부여합니다.
        예: {'김교수': 101, '박교수': 102, '이교수': 103, ...}
        """
        self.prof_map = {}
        unique_profs = df["교수명"].dropna().unique()
        for idx, prof_name in enumerate(unique_profs, start=101):
            self.prof_map[str(prof_name).strip()] = idx

    def parse_course_to_4_numbers(self, row):
        """
        한 과목(행)의 '시간표'(3개 숫자)와 '교수명'(1개 숫자)을 합쳐
        총 4개의 숫자 리스트(예: [11, 12, 31, 101])로 변환합니다.
        - 앞의 3개 숫자(2자리): 수업이 열리는 요일+교시 (예: 월1=11, 월2=12, 수1=31)
        - 마지막 4번째 숫자(3자리): 담당 교수님 고유 번호 (예: 김교수=101, 박교수=102)
        -> 이렇게 하면 과목명과 시간대가 완전히 똑같아도 교수가 다르면 4번째 숫자로 구별됩니다!
        """
        numeric_codes = []
        time_str = str(row["시간표"])
        prof_name = str(row["교수명"]).strip()

        # 1. 시간표 문자열을 쪼개어 시간 숫자(3개) 추출
        parts = time_str.split(",")
        for part in parts:
            clean_part = part.strip()
            if len(clean_part) >= 2:
                day_char = clean_part[0]
                period_str = clean_part[1:]

                if day_char in self.day_map and period_str.isdigit():
                    day_code = self.day_map[day_char]
                    period_num = int(period_str)
                    numeric_codes.append(day_code + period_num)

        # 2. 마지막 4번째 숫자로 교수님 고유 번호(101~) 추가
        prof_code = self.prof_map.get(prof_name, 999)
        numeric_codes.append(prof_code)

        return numeric_codes

    def process_dataframe(self, df):
        """
        전체 데이터프레임에 대해 교수 번호 매핑을 만든 뒤,
        4개의 숫자로 구성된 '수치화_시간표' 열과 장바구니 구분용 '강좌선택명' 열을 추가합니다.
        """
        processed_df = df.copy()

        # 교수님 고유 번호 사전 생성 (101번~)
        self.build_professor_map(processed_df)

        # 각 행마다 [교시1, 교시2, 교시3, 교수코드] 형태의 4개 숫자 리스트 생성
        processed_df["수치화_시간표"] = processed_df.apply(
            self.parse_course_to_4_numbers, axis=1
        )

        # 같은 과목명·같은 시간대·다른 교수 강의를 장바구니에서 쉽게 구별하도록 표시 이름 생성
        processed_df["강좌선택명"] = (
            processed_df["과목명"]
            + " ("
            + processed_df["교수명"]
            + " | "
            + processed_df["시간표"]
            + ")"
        )

        return processed_df

    def code_to_korean(self, code):
        """
        시간 숫자 코드(예: 11)를 다시 사람이 읽기 쉬운 한글(예: '월1교시')로 변환합니다.
        """
        day_prefix = code // 10
        period = code % 10
        day_char = self.reverse_day_map.get(day_prefix, "?")
        return f"{day_char}{period}교시"


# =====================================================================
# [Module B] ConflictChecker: 시간표 충돌 검사 클래스 (담당자 2)
# =====================================================================
class ConflictChecker:
    """
    사용자가 선택한 과목들 사이에 겹치는 시간(충돌)이 있는지
    파이썬의 집합(Set) 교집합 연산을 이용해 검사하는 클래스입니다.
    """

    def __init__(self, data_processor):
        self.dp = data_processor

    def check_conflicts(self, selected_df):
        """
        선택된 과목들의 4개 숫자 코드 중 앞의 '시간 숫자(100 미만)'들을 집합(Set)으로 만들어
        교집합(&)이 발생하는지 확인합니다.
        """
        has_conflict = False
        conflict_messages = []

        courses = selected_df.to_dict("records")
        num_courses = len(courses)

        for i in range(num_courses):
            for j in range(i + 1, num_courses):
                course_a = courses[i]
                course_b = courses[j]

                # 4개의 숫자 [교시1, 교시2, 교시3, 교수번호] 중에서
                # 시간표 충돌 검사는 실제 수업 시간인 앞의 숫자들(100 미만인 2자리 교시 코드)만 추출하여 비교합니다.
                # (만약 교수 번호까지 교집합에 넣으면, 같은 교수님의 서로 다른 시간대 수업을 들을 때 오류 충돌이 나기 때문!)
                time_set_a = set(code for code in course_a["수치화_시간표"] if code < 100)
                time_set_b = set(code for code in course_b["수치화_시간표"] if code < 100)

                # 두 과목의 수업 시간 교집합(&) 구하기
                overlap = time_set_a & time_set_b

                if overlap:
                    has_conflict = True
                    overlap_korean = [
                        self.dp.code_to_korean(code) for code in sorted(overlap)
                    ]
                    overlap_str = ", ".join(overlap_korean)

                    # 같은 과목명이라도 교수가 다를 수 있으므로 과목명(교수명)으로 명확히 표시
                    name_a = f"{course_a['과목명']}({course_a['교수명']})"
                    name_b = f"{course_b['과목명']}({course_b['교수명']})"
                    msg = f"'{name_a}' 강의와 '{name_b}' 강의가 [{overlap_str}]에 중복됩니다!"
                    conflict_messages.append(msg)

        return has_conflict, conflict_messages


# =====================================================================
# [Module C] FreeTimeAnalyzer: 공강 시간 분석 및 추천 클래스 (담당자 3)
# =====================================================================
class FreeTimeAnalyzer:
    """
    충돌이 없는 시간표에서 같은 요일의 수업과 수업 사이에 비어있는 '공강 시간'을 계산하고,
    최대 연속 공강 시간에 맞는 대학 생활 활동을 추천하는 클래스입니다.
    """

    def __init__(self):
        self.day_names = {1: "월요일", 2: "화요일", 3: "수요일", 4: "목요일", 5: "금요일"}

    def analyze_free_time(self, selected_df):
        """
        요일별로 교시를 오름차순 정렬한 뒤, 인접한 수업 사이의 빈 시간(공강)을 계산합니다.
        """
        day_periods = {1: [], 2: [], 3: [], 4: [], 5: []}

        for code_list in selected_df["수치화_시간표"]:
            for code in code_list:
                # 4번째 숫자인 교수 고유 번호(101 이상)는 건너뛰고, 시간 코드(100 미만)만 분석
                if code < 100:
                    day_num = code // 10
                    period_num = code % 10
                    if day_num in day_periods:
                        day_periods[day_num].append(period_num)

        max_gap = 0
        max_gap_info = ""
        daily_free_list = []

        for day_num, periods in day_periods.items():
            if len(periods) >= 2:
                sorted_periods = sorted(list(set(periods)))

                for i in range(len(sorted_periods) - 1):
                    current_p = sorted_periods[i]
                    next_p = sorted_periods[i + 1]

                    gap = next_p - current_p - 1

                    if gap > 0:
                        day_name = self.day_names[day_num]
                        free_start = current_p + 1
                        free_end = next_p - 1

                        if free_start == free_end:
                            gap_desc = f"{day_name} {free_start}교시 ({gap}시간 공강)"
                        else:
                            gap_desc = f"{day_name} {free_start}~{free_end}교시 ({gap}시간 연속 공강)"

                        daily_free_list.append(gap_desc)

                        if gap > max_gap:
                            max_gap = gap
                            max_gap_info = gap_desc

        if max_gap == 0:
            recommendation = "수업 사이 빈 공강 시간이 없습니다! 압축적인 시간표네요. 건강을 위해 간단한 간식을 챙겨 다니세요."
        elif max_gap == 1:
            recommendation = "최대 1시간 공강이 있습니다. 학생식당에서 여유롭게 식사하거나 카페에서 커피 한 잔 하며 다음 수업을 준비하기 좋습니다."
        elif max_gap == 2:
            recommendation = "최대 2시간 연속 공강이 있습니다. 중앙도서관 열람실에서 과제를 미리 해결하거나, 교내 헬스장/휴게실을 이용해 보세요."
        else:
            recommendation = f"최대 {max_gap}시간의 긴 연속 공강이 있습니다! 도서관 팀플/스터디 모임을 잡거나, 교내 근로장학 또는 어학 특강 수강을 강력히 추천합니다."

        return max_gap, max_gap_info, daily_free_list, recommendation


# =====================================================================
# [Module D] StreamlitDashboard: UI 렌더링 및 통합 클래스 (담당자 4)
# =====================================================================
class StreamlitDashboard:
    """
    Module A, B, C를 하나로 연결하고, Streamlit을 사용해
    넓은 왼쪽 사이드바 장바구니, 시간표 그리드, 하단 개설 과목 목록을 화면에 그리는 클래스입니다.
    """

    def __init__(self):
        self.processor = DataProcessor()
        self.checker = ConflictChecker(self.processor)
        self.analyzer = FreeTimeAnalyzer()

    def apply_custom_style(self):
        """
        왼쪽 사이드바의 폭을 넓히고, 장바구니에 선택한 과목이 스크롤 없이
        한눈에 다 보이도록 CSS 스타일을 적용하는 메서드입니다.
        """
        st.markdown(
            """
            <style>
            /* 1. 왼쪽 사이드바 가로 너비를 430px로 넉넉하게 확대 */
            [data-testid="stSidebar"] {
                min-width: 430px !important;
                max-width: 460px !important;
            }
            /* 2. 다중 선택(Multiselect) 박스에서 선택된 과목들이 스크롤에 가려지지 않고 전부 보이도록 높이 제한 해제 */
            [data-baseweb="select"] > div {
                max-height: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def create_timetable_grid(self, selected_df):
        """
        선택한 과목들을 요일(열)과 1~9교시(행) 기준의 2차원 표(DataFrame)로 변환합니다.
        """
        days = ["월", "화", "수", "목", "금"]
        periods = [f"{i}교시" for i in range(1, 10)]

        grid_df = pd.DataFrame("", index=periods, columns=days)
        num_to_day = {1: "월", 2: "화", 3: "수", 4: "목", 5: "금"}

        for _, row in selected_df.iterrows():
            course_name = row["과목명"]
            prof_name = row["교수명"]
            cell_text = f"{course_name} ({prof_name})"

            for code in row["수치화_시간표"]:
                # 4번째 숫자인 교수 번호(100 이상)는 제외하고 교시 코드(100 미만)만 시간표 칸에 표시
                if code < 100:
                    day_num = code // 10
                    period_num = code % 10

                    if day_num in num_to_day and 1 <= period_num <= 9:
                        day_col = num_to_day[day_num]
                        period_row = f"{period_num}교시"

                        if grid_df.loc[period_row, day_col] != "":
                            grid_df.loc[period_row, day_col] += f" / [충돌!] {cell_text}"
                        else:
                            grid_df.loc[period_row, day_col] = cell_text

        return grid_df

    def run(self):
        """
        대시보드 웹 애플리케이션을 실행하는 메인 메서드입니다.
        """
        st.set_page_config(page_title="수강 시간표 대시보드", layout="wide")
        self.apply_custom_style()

        st.title("📅 수강 시간표 충돌 검사 및 공강 시각화 대시보드")
        st.write("왼쪽 사이드바에서 **엑셀 파일을 업로드**하고 수강할 강의를 장바구니에 담아보세요.")

        # --- [Module A 호출] 파일 업로드 및 데이터 정제 ---
        st.sidebar.header("📂 1. 교과목 엑셀 파일 업로드")
        uploaded_file = st.sidebar.file_uploader(
            "개설 교과목 Excel(.xlsx) 또는 CSV 파일을 업로드하세요:",
            type=["xlsx", "csv"],
        )

        raw_df = self.processor.load_data(uploaded_file)

        # 파일이 아직 업로드되지 않았을 때 안내 화면 표시
        if raw_df is None:
            st.info("👈 먼저 왼쪽 사이드바에서 **`수강편람_40과목.xlsx`** 파일을 업로드해 주세요!")
            st.markdown(
                """
                **[안내] 생성된 엑셀 파일 위치:**
                - `C:\\Class\\수강편람_40과목.xlsx`
                - 총 **40개 과목**이 들어있으며, **과목명과 시간대가 같지만 담당교수가 다른 5쌍(10개 강좌)**이 포함되어 있습니다.
                - 각 강의는 `[교시1, 교시2, 교시3, 교수고유번호]` 총 **4개의 숫자**로 변환되어 구별됩니다.
                """
            )
            return

        processed_df = self.processor.process_dataframe(raw_df)

        # --- 왼쪽 사이드바: 장바구니 담기 시스템 ---
        st.sidebar.header("🛒 2. 수강 과목 장바구니 담기")
        all_course_labels = processed_df["강좌선택명"].tolist()

        # 처음 파일 업로드 시 예시로 3개 과목 기본 선택
        default_selection = (
            [all_course_labels[0], all_course_labels[4], all_course_labels[6]]
            if len(all_course_labels) >= 7
            else []
        )

        selected_labels = st.sidebar.multiselect(
            "수강할 강의를 클릭해서 추가/제거하세요 (과목명 | 교수명 | 시간표):",
            options=all_course_labels,
            default=default_selection,
        )

        # 사용자가 선택한 강의만 필터링 (교수님까지 구분된 '강좌선택명' 기준)
        selected_df = processed_df[processed_df["강좌선택명"].isin(selected_labels)]

        # 왼쪽 사이드바 하단에 '내가 담은 과목 표'를 스크롤 없이 한눈에 출력
        st.sidebar.markdown("---")
        st.sidebar.subheader(
            f"✅ 내가 담은 과목 ({len(selected_df)}과목 / 총 {selected_df['학점'].sum()}학점)"
        )
        if not selected_df.empty:
            st.sidebar.table(
                selected_df[["과목명", "교수명", "학점", "시간표", "수치화_시간표"]].reset_index(drop=True)
            )
        else:
            st.sidebar.info("아직 장바구니에 담긴 과목이 없습니다.")

        # --- 오른쪽 메인 화면 구성 ---
        if selected_df.empty:
            st.info("👈 왼쪽 사이드바 장바구니에서 수강할 과목을 1개 이상 선택해 주세요.")
        else:
            # --- [Module B 호출] 시간표 충돌 검사 ---
            has_conflict, conflict_messages = self.checker.check_conflicts(selected_df)

            if has_conflict:
                st.error("🚨 **시간표 충돌이 감지되었습니다! 아래 강의들의 시간을 확인해 주세요.**")
                for msg in conflict_messages:
                    st.error(f"- {msg}")
            else:
                st.success("✅ 선택한 강의들 사이에 시간표 충돌이 없습니다!")

            # --- 상단: 주간 시간표(왼쪽) & 공강 분석(오른쪽) ---
            col1, col2 = st.columns([3, 2])

            with col1:
                st.subheader("🗓️ 나의 주간 시간표 (1~9교시)")
                timetable_grid = self.create_timetable_grid(selected_df)
                st.dataframe(timetable_grid, use_container_width=True, height=360)

            with col2:
                st.subheader("⏳ 공강 시간 분석 및 추천 (Module C)")
                if has_conflict:
                    st.warning("먼저 시간표 충돌을 해결해야 정확한 공강 시간을 분석할 수 있습니다.")
                else:
                    # [Module C 호출] 공강 시간 분석
                    max_gap, max_gap_info, daily_free_list, recommendation = (
                        self.analyzer.analyze_free_time(selected_df)
                    )

                    total_credits = selected_df["학점"].sum()
                    metric_col1, metric_col2 = st.columns(2)
                    metric_col1.metric("총 신청 학점", f"{total_credits} 학점")
                    metric_col2.metric("최대 연속 공강", f"{max_gap} 시간")

                    st.markdown("**📌 요일별 수업 사이 공강 내역:**")
                    if daily_free_list:
                        for item in daily_free_list:
                            st.write(f"- {item}")
                    else:
                        st.write("- 수업과 수업 사이에 끼어있는 공강이 없습니다.")

                    st.info(f"💡 **맞춤형 활동 추천:**\n\n{recommendation}")

        # --- 하단: 전체 개설 교과목 목록 (시간표 아래에 배치) ---
        st.divider()
        st.subheader(f"📋 전체 개설 교과목 목록 (총 {len(processed_df)}개 강좌)")
        st.caption(
            "수치화_시간표 열의 4개 숫자는 [교시1, 교시2, 교시3, 교수고유번호(101~)]를 의미합니다. "
            "과목명과 시간대가 같아도 담당교수가 다르면 4번째 숫자가 달라집니다."
        )
        display_cols = ["과목명", "교수명", "이수구분", "학점", "시간표", "수치화_시간표"]
        st.dataframe(processed_df[display_cols], use_container_width=True, height=420)


# =====================================================================
# 프로그램 시작점 (Entry Point)
# =====================================================================
if __name__ == "__main__":
    app = StreamlitDashboard()
    app.run()
