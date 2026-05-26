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
    """학생식당 빈 코너 템플릿 생성"""
    return [
        {"corner": "덮밥 / 비빔밥", "icon": "bowl", "items": []},
        {"corner": "면류 / 찌개", "icon": "soup", "items": []},
        {"corner": "볶음밥 / 오므라이스 / 돈까스", "icon": "utensils-crossed", "items": []}
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
    """학생 식당 메뉴 추출 (1주일 마스터 메뉴 생성 후 5일 복사)"""
    soup = BeautifulSoup(html, 'html.parser')
    master_menu = get_empty_student_menu()
    
    tables = soup.find_all('table')
    if not tables:
        return [copy.deepcopy(master_menu) for _ in range(5)]

    text_content = tables[0].get_text(separator='\n')
    lines = text_content.split('\n')
    
    price_pattern = re.compile(r'([1-9][0-9]*,?[0-9]{3})(?:원)?')
    seen_items = set()
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        line = line.replace('ⓣ', '').strip()
        match = price_pattern.search(line)
        
        if match:
            price_str = match.group(1)
            price_val = price_str.replace(',', '')
            if not price_val.endswith('00'):
                continue
                
            name = line.replace(price_str, '').replace('원', '').strip()
            
            # 잘못 섞여 들어간 요일 헤더(예: (월)) 텍스트 청소
            name = re.sub(r'\([월화수목금]\)', '', name).strip()
            
            if not name or name in seen_items:
                continue
            seen_items.add(name)
            
            item = {"name": name, "price": f"{price_str}원"}
            
            # 코너 자동 분류
            if any(keyword in name for keyword in ['면', '라면', '찌개', '모밀', '국수', '우동', '짬뽕']):
                master_menu[1]['items'].append(item)
            elif any(keyword in name for keyword in ['돈까스', '오므라이스', '볶음밥', '치즈볼', '카츠']):
                master_menu[2]['items'].append(item)
            else:
                master_menu[0]['items'].append(item)

    # 완성된 마스터 메뉴를 월~금(5일)에 똑같이 복사하여 반환
    return [copy.deepcopy(master_menu) for _ in range(5)]

def parse_staff_menu(html):
    """교직원 식당 메뉴 추출 (표의 열(Column) 위치 기반 매핑)"""
    soup = BeautifulSoup(html, 'html.parser')
    staff_menus = [[] for _ in range(5)] # 월~금 빈 리스트
    
    tables = soup.find_all('table')
    if not tables:
        return staff_menus
        
    for table in tables:
        # 칸(Column) 인덱스(0,1,2..)가 무슨 요일(월,화..)인지 기억하는 사전
        col_to_day = {} 
        rows = table.find_all('tr')
        
        for row in rows:
            cells = row.find_all(['th', 'td'])
            cell_idx = 0
            
            for cell in cells:
                text = cell.get_text(separator=' ', strip=True)
                
                # 1. 이 칸이 무슨 요일인지 찾아서 매핑 (예: 2번째 칸은 (화)요일)
                day_match = re.search(r'\(([월화수목금])\)', text)
                if day_match:
                    day_idx = ['월', '화', '수', '목', '금'].index(day_match.group(1))
                    col_to_day[cell_idx] = day_idx
                    
                # 2. 밥/반찬 텍스트가 발견되면
                if '밥' in text and ('국' in text or '찌개' in text or '김치' in text or '샐러드' in text):
                    # 원산지 괄호 삭제 및 공백/특수문자 기준 분리
                    text_no_brackets = re.sub(r'\([^)]*\)', '', text)
                    raw_menus = re.split(r'[,/\s]+', text_no_brackets)
                    clean_menus = [m.strip() for m in raw_menus if len(m.strip()) > 1]
                    
                    # 현재 칸(cell_idx)에 해당하는 요일(target_day) 찾기
                    target_day = col_to_day.get(cell_idx, -1)
                    
                    # 혹시 표 구조가 이상해서 요일을 못 찾았을 경우, 빈칸에 순서대로 채워 넣는 방어 로직
                    if target_day == -1:
                        for d in range(5):
                            if not staff_menus[d]:
                                target_day = d
                                break
                                
                    # 정해진 요일 위치에 데이터 삽입
                    if target_day != -1:
                        staff_menus[target_day] = [{
                            "type": "중식",
                            "time": "11:30 ~ 13:30",
                            "menus": clean_menus,
                            "price": "6,000원"
                        }]
                
                # colspan 속성이 있으면 그만큼 열 인덱스를 건너뜀 (표 엉킴 방지)
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
    
    # 요일별(월~금, 인덱스 0~4)로 학생/교직원 데이터 결합
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
