
from bs4 import BeautifulSoup

def extract_tile_structure(html_file):
    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    title_el = soup.select_one('[data-testid="product-title"]')
    if title_el:
        print(f"Product title text: {title_el.get_text(strip=True)}")
        curr = title_el
        for i in range(10):
            curr = curr.parent
            if not curr: break
            print(f"Parent level {i+1}: {curr.name} classes={curr.get('class', [])} data-testid={curr.get('data-testid')}")
            # Check for price at this level
            price = curr.select_one('[data-testid="price-product-tile"]') or curr.select_one('[data-testid="sale-price"]')
            if price:
                print(f"  --> Found price at this level: {price.get_text(strip=True)}")

if __name__ == "__main__":
    extract_tile_structure("/tmp/provigo_deals_load.html")
