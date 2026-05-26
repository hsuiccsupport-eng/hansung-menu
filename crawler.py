import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta

# 한성대학교 식당 메뉴 URL
URL_STUDENT = "https://hansung.ac.kr/hansung/6332/subview.do"
URL_STAFF = "https://hansung.ac.kr/hansung/6333/subview.do"

def get_this_week_dates():
    """이번 주 월~금의 날짜 문자열(YYYY-MM-DD) 리스트를 반환합니다."""
    today = datetime.today()
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
    """학생 식당 HTML에서 요일별 메뉴 데이터를 추출합니다."""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 5일치(월~금) 빈 데이터를 미리 생성
    daily_menus = [get_empty_student_menu() for _ in range(5)]
    
    tables = soup.find_all('table')
    if not tables:
        return daily_menus

    text_content = tables[0].get_text(separator='\n')
    lines = text_content.split('\n')
    
    price_pattern = re.compile(r'([1-9][0-9]*,?[0-9]{3})(?:원)?')
    
    # 기본적으로 5일 전체에 공통 적용된다고 가정 (메뉴가 1주일 내내 동일할 경우)
    target_days = [0, 1, 2, 3, 4]
    seen_items_per_day = [set() for _ in range(5)]
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 요일 감지 (해당 요일이 나오면, 그 이후의 메뉴는 해당 요일에만 적용)
        day_match = re.search(r'\(([월화수목금])\)', line)
        if day_match:
            day_char = day_match.group(1)
            day_idx = ['월', '화', '수', '목', '금'].index(day_char)
            target_days = [day_idx] # 타겟 요일 변경
            continue
            
        line = line.replace('ⓣ', '').strip()
        match = price_pattern.search(line)
        
        if match:
            price_str = match.group(1)
            price_val = price_str.replace(',', '')
            if not price_val.endswith('00'):
                continue
                
            name = line.replace(price_str, '').replace('원', '').strip()
            item = {"name": name, "price": f"{price_str}원"}
            
            # 지정된 타겟 요일들에 메뉴 추가
            for d_idx in target_days:
                if name in seen_items_per_day[d_idx]:
                    continue
                seen_items_per_day[d_idx].add(name)
                
                # 코너 분류
                if any(keyword in name for keyword in ['면', '라면', '찌개', '모밀', '국수', '우동', '짬뽕']):
                    daily_menus[d_idx][1]['items'].append(item)
                elif any(keyword in name for keyword in ['돈까스', '오므라이스', '볶음밥', '치즈볼', '카츠']):
                    daily_menus[d_idx][2]['items'].append(item)
                else:
                    daily_menus[d_idx][0]['items'].append(item)

    return daily_menus

def parse_staff_menu(html):
    """교직원 식당 HTML에서 요일별 메뉴 데이터를 추출합니다."""
    soup = BeautifulSoup(html, 'html.parser')
    staff_menu_list = []
    
    tables = soup.find_all('table')
    if not tables:
        return [[] for _ in range(5)]
        
    rows = tables[0].find_all('tr')
    
    for row in rows:
        cells = row.find_all(['th', 'td'])
        cells_text = [cell.get_text(strip=True, separator=' ') for cell in cells]
        
        for text in cells_text:
            if '밥' in text and ('국' in text or '찌개' in text or '김치' in text or '샐러드' in text):
                text_no_brackets = re.sub(r'\([^)]*\)', '', text)
                raw_menus = re.split(r'[,/\s]+', text_no_brackets)
                clean_menus = [m.strip() for m in raw_menus if len(m.strip()) > 1]
                
                staff_menu_list.append([{
                    "type": "중식",
                    "time": "11:30 ~ 13:30",
                    "menus": clean_menus,
                    "price": "6,000원"
                }])
                break
                
        if len(staff_menu_list) >= 5:
            break

    # 홈페이지에 식단이 5일치 미만으로 올라왔을 경우 빈 공간 채우기
    while len(staff_menu_list) < 5:
        staff_menu_list.append([])

    return staff_menu_list

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
    
    # 요일별(0~4)로 묶어서 JSON 구조화
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
