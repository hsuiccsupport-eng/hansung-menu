import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

# 한성대학교 식당 메뉴 URL
URL_STUDENT = "https://hansung.ac.kr/hansung/6332/subview.do"
URL_STAFF = "https://hansung.ac.kr/hansung/6333/subview.do"

def get_html(url):
    """지정된 URL에서 HTML 콘텐츠를 가져옵니다."""
    try:
        # User-Agent 설정: 봇으로 인식되어 차단되는 것을 방지합니다.
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status() # 오류 발생 시 예외 처리
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {url}\n{e}")
        return None

def parse_student_menu(html):
    """학생 식당 HTML에서 메뉴 데이터를 추출합니다."""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 3가지 코너 기본 템플릿
    student_menu = [
        {"corner": "덮밥 / 비빔밥", "icon": "bowl", "items": []},
        {"corner": "면류 / 찌개", "icon": "soup", "items": []},
        {"corner": "볶음밥 / 오므라이스 / 돈까스", "icon": "utensils-crossed", "items": []}
    ]
    
    # 홈페이지의 표(Table)에서 텍스트를 추출
    tables = soup.find_all('table')
    if not tables:
        return student_menu

    # 학생식당 메뉴 테이블 텍스트 긁어오기
    text_content = tables[0].get_text(separator='\n')
    lines = text_content.split('\n')
    
    # 정규표현식: 가격 형태 (예: 5,000 또는 4500) 찾기
    price_pattern = re.compile(r'([0-9,]{4,})(?:원)?')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # [수정된 부분] 테이크아웃(ⓣ) 기호가 있는 메뉴는 제외 (건너뛰기)
        if 'ⓣ' in line:
            continue
            
        match = price_pattern.search(line)
        if match:
            price_str = match.group(1)
            # 가격 부분을 제외한 나머지를 메뉴 이름으로 추출
            name = line.replace(price_str, '').replace('원', '').strip()
            
            # 메뉴 이름 키워드에 따라 3개 코너로 자동 분류
            item = {"name": name, "price": f"{price_str}원"}
            
            if any(keyword in name for keyword in ['면', '라면', '찌개', '모밀', '국수']):
                student_menu[1]['items'].append(item)
            elif any(keyword in name for keyword in ['돈까스', '오므라이스', '볶음밥', '치즈볼']):
                student_menu[2]['items'].append(item)
            else:
                student_menu[0]['items'].append(item) # 나머지는 덮밥/비빔밥으로 분류

    return student_menu

def parse_staff_menu(html):
    """교직원 식당 HTML에서 메뉴 데이터를 추출합니다."""
    soup = BeautifulSoup(html, 'html.parser')
    staff_menu = []
    
    tables = soup.find_all('table')
    if not tables:
        return staff_menu
        
    # 교직원 식당 테이블 분석
    rows = tables[0].find_all('tr')
    
    for row in rows:
        cells = row.find_all(['th', 'td'])
        cells_text = [cell.get_text(strip=True, separator=' ') for cell in cells]
        
        # 밥(백미/흑미 등) 키워드가 있는 셀을 오늘의 메뉴로 간주
        for text in cells_text:
            if '밥' in text and ('국' in text or '찌개' in text or '김치' in text):
                # 쉼표나 공백 등으로 나열된 반찬 분리
                raw_menus = re.split(r'[,/]+|\s{2,}', text)
                clean_menus = [m.strip() for m in raw_menus if len(m.strip()) > 1]
                
                staff_menu.append({
                    "type": "중식",
                    "time": "11:30 ~ 13:30",
                    "menus": clean_menus[:7], # UI를 위해 최대 7개 반찬만 표시
                    "price": "6,000원" # 기본 단가
                })
                break # 메뉴를 찾으면 종료
        
        if staff_menu:
            break

    return staff_menu

def main():
    """크롤링 메인 함수"""
    print("--- 학식 메뉴 크롤링 시작 ---")
    
    # 1. HTML 가져오기
    html_student = get_html(URL_STUDENT)
    html_staff = get_html(URL_STAFF)
    
    if not html_student or not html_staff:
        print("HTML을 가져오지 못해 크롤링을 중단합니다.")
        return

    # 2. 데이터 추출 (파싱)
    student_data = parse_student_menu(html_student)
    staff_data = parse_staff_menu(html_staff)
    
    # 3. 데이터 구조화 (JSON 형태)
    menu_data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "student": student_data,
        "staff": staff_data
    }
    
    # 4. JSON 파일로 저장 (프론트엔드 UI에서 이 파일을 읽어들입니다)
    with open('menu_data.json', 'w', encoding='utf-8') as f:
        json.dump(menu_data, f, ensure_ascii=False, indent=4)
        
    print("--- 학식 메뉴 크롤링 완료 (menu_data.json 저장됨) ---")

if __name__ == "__main__":
    main()