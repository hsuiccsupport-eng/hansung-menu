import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta
import copy

# 한성대학교 식당 메뉴 URL
URL_STUDENT = "https://hansung.ac.kr/hansung/6332/subview.do"
URL_STAFF = "https://hansung.ac.kr/hansung/6333/subview.do"

def get_this_week_dates():
    """이번 주 월~금의 날짜 문자열(YYYY-MM-DD) 리스트를 반환합니다."""
    today = datetime.today()
    # 월요일 기준으로 이번 주 날짜 계산
    monday = today - timedelta(days=today.weekday())
    return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)]

def get_empty_student_menu():
    """학생식당 빈 코너 템플릿 생성 (유효한 Lucide 아이콘으로 교체)"""
    return [
        {"corner": "덮밥 / 비빔밥", "icon": "utensils", "items": []},
        {"corner": "면류 / 찌개", "icon": "soup", "items": []},
        {"corner": "볶음밥 / 오므라이스 / 돈까스", "icon": "chef-hat", "items": []}
    ]

def get_html(url):
    """지정된 URL에서 HTML 콘텐츠를 가져옵니다."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {url}\n{e}")
        return None

def parse_student_menu(html):
    """학생 식당 메뉴 추출 (표의 열 위치 및 예외 텍스트 완벽 분석)"""
    soup = BeautifulSoup(html, 'html.parser')
    daily_menus = [get_empty_student_menu() for _ in range(5)]
    
    tables = soup.find_all('table')
    if not tables:
        return daily_menus

    price_pattern = re.compile(r'([1-9][0-9]*,?[0-9]{3})(?:원)?')
    
    for table in tables:
        col_to_day = {}
        rows = table.find_all('tr')
        
        for row in rows:
            cells = row.find_all(['th', 'td'])
            cell_idx = 0
            
            for cell in cells:
                text = cell.get_text(separator='\n', strip=True)
                
                # 1. 요일 열(Column) 매핑
                day_match = re.search(r'\(([월화수목금])\)', text)
                if day_match:
                    day_idx = ['월', '화', '수', '목', '금'].index(day_match.group(1))
                    col_to_day[cell_idx] = day_idx
                    
                # 2. 해당 셀 내의 텍스트 줄별로 분석
                lines = text.split('\n')
                items_found = []
                
                for line in lines:
                    line = line.replace('ⓣ', '').strip()
                    match = price_pattern.search(line)
                    if match:
                        price_str = match.group(1)
                        price_val = price_str.replace(',', '')
                        if price_val.endswith('00'):
                            name = line.replace(price_str, '').replace('원', '').strip()
                            name = re.sub(r'\([월화수목금]\)', '', name).strip()
                            if name:
                                items_found.append({"name": name, "price": f"{price_str}원"})
                                
                colspan = int(cell.get('colspan', 1))
                
                # 3. "식단 없음" 명시적 체크 (월요일 공휴일 방어 로직)
                is_empty_day = "등록된 식단" in text or "없습니다" in text
                
                # 데이터가 있고 휴일이 아니라면 요일별로 집어넣기
                if items_found and not is_empty_day:
                    target_days = []
                    # 이 칸이 특정 요일 칸인 경우
                    if cell_idx in col_to_day:
                        target_days = [col_to_day[cell_idx]]
                    # 5일 전체 통합 칸(병합된 셀)인 경우
                    elif colspan >= 5:
                        target_days = [0, 1, 2, 3, 4]
                    # 요일 헤더를 아예 못 찾은 경우 5일치 복사
                    elif not col_to_day:
                        target_days = [0, 1, 2, 3, 4]
                        
                    for d in target_days:
                        if d < 5:
                            for item in items_found:
                                name = item['name']
                                # 중복 방지
                                existing = [x['name'] for corner in daily_menus[d] for x in corner['items']]
                                if name in existing:
                                    continue
                                    
                                # 코너 분류
                                if any(keyword in name for keyword in ['면', '라면', '찌개', '모밀', '국수', '우동', '짬뽕']):
                                    daily_menus[d][1]['items'].append(item)
                                elif any(keyword in name for keyword in ['돈까스', '오므라이스', '볶음밥', '치즈볼', '카츠']):
                                    daily_menus[d][2]['items'].append(item)
                                else:
                                    daily_menus[d][0]['items'].append(item)
                
                cell_idx += colspan

    return daily_menus

def parse_staff_menu(html):
    """교직원 식당 메뉴 추출 (표의 열(Column) 위치 기반 매핑)"""
    soup = BeautifulSoup(html, 'html.parser')
    staff_menus = [[] for _ in range(5)]
    
    tables = soup.find_all('table')
    if not tables:
        return staff_menus
        
    for table in tables:
        col_to_day = {} 
        rows = table.find_all('tr')
        
        for row in rows:
            cells = row.find_all(['th', 'td'])
            cell_idx = 0
            
            for cell in cells:
                text = cell.get_text(separator=' ', strip=True)
                
                # 요일 매핑
                day_match = re.search(r'\(([월화수목금])\)', text)
                if day_match:
                    day_idx = ['월', '화', '수', '목', '금'].index(day_match.group(1))
                    col_to_day[cell_idx] = day_idx
                    
                # 밥/반찬 텍스트 감지
                if '밥' in text and ('국' in text or '찌개' in text or '김치' in text or '샐러드' in text):
                    text_no_brackets = re.sub(r'\([^)]*\)', '', text)
                    raw_menus = re.split(r'[,/\s]+', text_no_brackets)
                    clean_menus = [m.strip() for m in raw_menus if len(m.strip()) > 1]
                    
                    target_day = col_to_day.get(cell_idx, -1)
                    
                    if target_day == -1:
                        for d in range(5):
                            if not staff_menus[d]:
                                target_day = d
                                break
                                
                    if target_day != -1:
                        staff_menus[target_day] = [{
                            "type": "중식",
                            "time": "11:30 ~ 13:30",
                            "menus": clean_menus,
                            "price": "6,000원"
                        }]
                
                colspan = int(cell.get('colspan', 1))
                cell_idx += colspan

    return staff_menus

def main():
    print("--- 학식 메뉴 크롤링 시작 ---")
    
    html_student = get_html(URL_STUDENT)
    html_staff = get_html(URL_STAFF)
    
    if not html_student or not html_staff:
        print("HTML을 가져오지 못해 크롤링을 중단합니다.")
        return

    student_data_list = parse_student_menu(html_student)
    staff_data_list = parse_staff_menu(html_staff)
    
    week_dates = get_this_week_dates()
    daily_menus = {}
    
    for i, date_str in enumerate(week_dates):
        daily_menus[date_str] = {
            "student": student_data_list[i],
            "staff": staff_data_list[i]
        }
    
    menu_data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "daily_menus": daily_menus
    }
    
    with open('menu_data.json', 'w', encoding='utf-8') as f:
        json.dump(menu_data, f, ensure_ascii=False, indent=4)
        
    print("--- 학식 메뉴 크롤링 완료 (menu_data.json 저장됨) ---")

if __name__ == "__main__":
    main()
