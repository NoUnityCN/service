import requests
import json
import time
import os


def get_unity_releases(version:str):
    url = "https://services.unity.com/graphql"
    
    headers = {
        "Authority": "services.unity.com",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Content-Type": "application/json",
        "Origin": "https://unity.com",
        "Referer": "https://unity.com/",
        "Sec-Ch-Ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Microsoft Edge";v="134"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
        "X-Client-Name": "web-platform-hexagon",
        "X-Client-Version": "1.0.0",
    }

    payload = {
        "operationName": "GetRelease",
        "variables": {
            "version": version,  # 使用新函数设置版本
            "limit": 300
        },
        "query": """query GetRelease($limit: Int, $skip: Int, $version: String!, $stream: [UnityReleaseStream!]) {
      getUnityReleases(
        limit: $limit
        skip: $skip
        stream: $stream
        version: $version
        entitlements: [XLTS]
      ) {
        totalCount
        edges {
          node {
            version
            entitlements
            releaseDate
            unityHubDeepLink
            stream
            __typename
          }
          __typename
        }
        __typename
      }
    }"""
    }

    response = None
    try:
        # 发送请求（启用自动解压）
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30  # 增加超时时间
        )
        response.raise_for_status()

        # 智能解压处理
        content = handle_content_encoding(response)

        # 解析JSON
        json_data = json.loads(content)
        
        # 提取数据
        process_response_data(json_data)
        
        # 返回所有版本的Unity Hub链接
        return categorize_releases(json_data)

    except requests.exceptions.RequestException as e:
        print(f"网络请求失败: {str(e)}")
        if response:
            debug_response(response)
    except json.JSONDecodeError:
        print("JSON 解析失败")
        if response:
            debug_response(response)
    except Exception as e:
        print(f"未处理异常: {str(e)}")
        if response:
            debug_response(response)
    
    return {}

def handle_content_encoding(response):
    """处理内容编码"""
    try:
        # 优先尝试自动解压
        if response.headers.get('Content-Encoding') == 'br':
            return decompress_brotli(response.content)
        return response.text
    except Exception as e:
        print(f"解压失败，尝试原始解码: {str(e)}")
        return response.content.decode('utf-8', errors='replace')

def decompress_brotli(data):
    """多重尝试 Brotli 解压"""
    try:
        # 优先使用 brotlicffi
        import brotlicffi as brotli
        return brotli.decompress(data).decode()
    except ImportError:
        try:
            # 备用方案：标准 brotli
            import brotli
            return brotli.decompress(data).decode()
        except Exception as e:
            raise ValueError(f"Brotli 解压失败: {str(e)}")

def process_response_data(json_data):
    """处理并格式化输出数据"""
    releases = json_data.get('data', {}).get('getUnityReleases', {})
    
    print(f"找到 {releases.get('totalCount', 0)} 个版本")
    for idx, edge in enumerate(releases.get('edges', []), 1):
        node = edge.get('node', {})
        print(f"\n版本 #{idx}:")
        print(f"• 版本号: {node.get('version')}")
        print(f"• 发布日期: {node.get('releaseDate')}")
        print(f"• 发布渠道: {node.get('stream')}")
        print(f"• Hub链接: {node.get('unityHubDeepLink')}")

def debug_response(response):
    """输出调试信息"""
    if not response:
        return
    
    print("\n" + "="*40 + " 调试信息 " + "="*40)
    print(f"状态码: {response.status_code}")
    print("响应头:")
    print(json.dumps(dict(response.headers), indent=2))
    
    if response.content:
        try:
            print("\n响应内容 (截取):")
            print(response.content[:200].decode('utf-8', errors='replace'))
        except:
            print("原始内容 (十六进制):")
            print(response.content[:100].hex())
    
    print("="*93 + "\n")

def categorize_releases(json_data):
    """将所有版本按类型分类"""
    releases = json_data.get('data', {}).get('getUnityReleases', {})
    edges = releases.get('edges', [])
    
    categories = {
        'LTS': [],
        'BETA': [],
        'ALPHA': [],
        'TECH': []
    }
    
    for edge in edges:
        node = edge.get('node', {})
        stream = node.get('stream', '')
        hub_link = node.get('unityHubDeepLink')
        version = node.get('version')
        
        if not hub_link:
            continue
            
        link_info = {
            'version': version,
            'link': hub_link
        }
        
        if 'LTS' in stream:
            categories['LTS'].append(link_info)
        elif 'BETA' in stream or 'beta' in stream.lower():
            categories['BETA'].append(link_info)
        elif 'ALPHA' in stream or 'alpha' in stream.lower():
            categories['ALPHA'].append(link_info)
        elif 'TECH' in stream:
            categories['TECH'].append(link_info)
    
    return categories

def save_results_to_json(all_versions_by_category):
    """将结果保存为JSON文件
    
    Args:
        all_versions_by_category: 包含所有版本的分类字典 
            格式: {'LTS': {'6000': [...], '2023': [...]}, 'BETA': {...}, ...}
    """
    # 确保输出目录存在
    output_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 为每个类别创建一个JSON文件
    for category, versions_dict in all_versions_by_category.items():
        filename = os.path.join(output_dir, f"{category}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(versions_dict, f, indent=2, ensure_ascii=False)
        print(f"已保存 {category} 版本到 {filename}")

if __name__ == "__main__":
    # 在这里直接指定要查询的版本
    versions = ["6000", "2023", "2022", "2021", "2020", "2019", "2018", "2017", "5"]
    
    # 收集所有版本数据，按类别分组
    all_versions_by_category = {
        'LTS': {},
        'BETA': {},
        'ALPHA': {},
        'TECH': {}
    }
    
    # 转换版本号为API需要的格式
    for i, version in enumerate(versions):
        print(f"\n===== 查询Unity {version} 版本 =====")
        categories = get_unity_releases(version)
        
        for category, releases in categories.items():
            if releases:
                print(f"\n{category} 版本 ({len(releases)}个):")
                # 提取这个类别下当前版本的所有链接
                links = [release['link'] for release in releases]
                
                # 添加到相应的类别中
                if version not in all_versions_by_category[category]:
                    all_versions_by_category[category][version] = links
                
                # 打印链接
                for link in links:
                    print(link)
        
        # 在多个版本请求之间添加间隔，避免服务器拒绝请求
        if i < len(versions) - 1:
            time.sleep(3)
    
    # 保存结果到JSON文件
    save_results_to_json(all_versions_by_category)