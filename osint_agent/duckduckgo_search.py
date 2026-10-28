"""
DuckDuckGo Search Tool - Free alternative to Google Search
ใช้ ddgs library - ไม่ต้องใช้ API Key, ฟรี 100%
"""

from ddgs import DDGS


def duckduckgo_search(query: str, max_results: int = 10) -> list:
    """
    ค้นหาด้วย DuckDuckGo

    Args:
        query: คำค้นหา (รองรับ operators: site:, OR, "exact")
        max_results: จำนวนผลลัพธ์สูงสุด

    Returns:
        list of dict: [{"title": "", "url": "", "snippet": ""}]
    """
    results = []

    try:
        ddgs = DDGS()
        search_results = ddgs.text(query, max_results=max_results)

        for result in search_results:
            results.append({
                "title": result.get("title", ""),
                "url": result.get("href", result.get("url", "")),
                "snippet": result.get("body", result.get("description", ""))
            })

    except Exception as e:
        print(f"DuckDuckGo search error: {e}")

    return results


def duckduckgo_search_lite(query: str, max_results: int = 10) -> list:
    """
    Alias for duckduckgo_search (for backward compatibility)
    """
    return duckduckgo_search(query, max_results)


def format_results(results: list) -> str:
    """
    Format search results เป็น text
    """
    if not results:
        return "ไม่พบผลลัพธ์"

    output = []
    for i, result in enumerate(results, 1):
        title = result.get("title", "ไม่มีหัวข้อ")
        url = result.get("url", "")
        snippet = result.get("snippet", "")

        output.append(f"{i}. {title}")
        output.append(f"   URL: {url}")
        if snippet:
            output.append(f"   {snippet[:200]}")
        output.append("")

    return "\n".join(output)


# Test function
if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, errors='replace')

    print("Testing DuckDuckGo Search...")
    results = duckduckgo_search("Linus Torvalds", max_results=5)
    print(f"\nFound {len(results)} results:\n")

    if results:
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['title']}")
            print(f"   {r['url']}")
            if r.get('snippet'):
                print(f"   {r['snippet'][:100]}")
            print()
    else:
        print("No results found")
