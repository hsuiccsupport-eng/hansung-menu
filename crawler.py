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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {url}\n{e}")
        return None

def parse_student_menu(html):
    """학생 식당 HTML에서 메뉴 데이터를 추출합니다."""
    soup = BeautifulSoup(html, 'html.parser')
    
    student_menu = [
        {"corner": "덮밥 / 비빔밥", "icon": "bowl", "items": []},
        {"corner": "면류 / 찌개", "icon": "soup", "items": []},
        {"corner": "볶음밥 / 오므라이스 / 돈까스", "icon": "utensils-crossed", "items": []}
    ]
    
    tables = soup.find_all('table')
    if not tables:
        return student_menu

    text_content = tables[0].get_text(separator='\n')
    lines = text_content.split('\n')
    
    # 정규표현식: 날짜 요일 패턴 찾기 (예: (월), (화))
    date_pattern = re.compile(r'\([월화수목금토일]\)')
    # 정규표현식: 가격 형태 찾기 (3자리 이상 숫자 콤마 포함)
    price_pattern = re.compile(r'([1-9][0-9]*,?[0-9]{3})(?:원)?')
    
    # 중복 메뉴 방지를 위한 세트(Set)
    seen_items = set()
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 1. 날짜가 포함된 줄(예: 2026.05.25 (월))은 메뉴가 아니므로 건너뛰기
        if date_pattern.search(line):
            continue
            
        # 2. 테이크아웃(ⓣ) 기호는 화면을 위해 깔끔하게 제거하되 메뉴는 살림
        line = line.replace('ⓣ', '').strip()
            
        match = price_pattern.search(line)
        if match:
            price_str = match.group(1)
            
            # 3. 우연히 4자리 숫자가 잡히는 것을 방지 (학식 가격은 보통 00으로 끝남)
            price_val = price_str.replace(',', '')
            if not price_val.endswith('00'):
                continue
                
            name = line.replace(price_str, '').replace('원', '').strip()
            
            # 4. 중복 검사: 이미 들어간 메뉴라면 추가하지 않음
            if name in seen_items:
                continue
            seen_items.add(name)
            
            item = {"name": name, "price": f"{price_str}원"}
            
            # 5. 코너 분류
            if any(keyword in name for keyword in ['면', '라면', '찌개', '모밀', '국수']):
                student_menu[1]['items'].append(item)
            elif any(keyword in name for keyword in ['돈까스', '오므라이스', '볶음밥', '치즈볼']):
                student_menu[2]['items'].append(item)
            else:
                student_menu[0]['items'].append(item)

    return student_menu

def parse_staff_menu(html):
    """교직원 식당 HTML에서 메뉴 데이터를 추출합니다."""
    soup = BeautifulSoup(html, 'html.parser')
    staff_menu = []
    
    tables = soup.find_all('table')
    if not tables:
        return staff_menu
        
    rows = tables[0].find_all('tr')
    
    for row in rows:
        cells = row.find_all(['th', 'td'])
        cells_text = [cell.get_text(strip=True, separator=' ') for cell in cells]
        
        for text in cells_text:
            if '밥' in text and ('국' in text or '찌개' in text or '김치' in text):
                raw_menus = re.split(r'[,/]+|\s{2,}', text)
                clean_menus = [m.strip() for m in raw_menus if len(m.strip()) > 1]
                
                staff_menu.append({
                    "type": "중식",
                    "time": "11:30 ~ 13:30",
                    "menus": clean_menus[:7],
                    "price": "6,000원"
                })
                break
        
        if staff_menu:
            break

    return staff_menu

def main():
    print("--- 학식 메뉴 크롤링 시작 ---")
    
    html_student = get_html(URL_STUDENT)
    html_staff = get_html(URL_STAFF)
    
    if not html_student or not html_staff:
        print("HTML을 가져오지 못해 크롤링을 중단합니다.")
        return

    student_data = parse_student_menu(html_student)
    staff_data = parse_staff_menu(html_staff)
    
    menu_data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "student": student_data,
        "staff": staff_data
    }
    
    with open('menu_data.json', 'w', encoding='utf-8') as f:
        json.dump(menu_data, f, ensure_ascii=False, indent=4)
        
    print("--- 학식 메뉴 크롤링 완료 (menu_data.json 저장됨) ---")

if __name__ == "__main__":
    main()
