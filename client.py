#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import socket
import time
import json
import pandas as pd
import re
import os
import numpy as np

# 第一部分：通用基础工具函数 
def is_empty(x) -> bool:
    """判断是否空值/NULL/空字符串"""
    if x is None:
        return True
    s = str(x).strip()
    if s == "":
        return True
    if s.upper() == "NULL":
        return True
    if s.lower() == "nan":
        return True
    return False

def read_raw_csv_for_clean(path: str) -> pd.DataFrame:
    """读取无表头的原始乱码 CSV"""
    df = pd.read_csv(
        path,
        header=None,
        dtype=str,
        keep_default_na=False,
        engine="python",
        encoding="utf-8-sig",
    )
    return df

def ensure_columns(df: pd.DataFrame, needed_max_col_index: int) -> pd.DataFrame:
    if df.shape[1] <= needed_max_col_index:
        df = df.reindex(columns=list(range(needed_max_col_index + 1)), fill_value="")
    return df

# 第二部分：清洗A类文件 
def clean_a_specific(raw_path: str, out_path: str) -> pd.DataFrame:
    """针对 A.xlsx 的专门清洗逻辑"""
    print(f"   正在读取并清洗 A类文件: {raw_path} ...")
    
    df = None
    try:
        df = pd.read_excel(raw_path, dtype=str)
    except Exception:
        for enc in ["utf-8", "gbk", "utf-8-sig"]:
            try:
                df = pd.read_csv(raw_path, encoding=enc, dtype=str)
                break
            except:
                pass
    
    if df is None:
        raise ValueError("无法读取文件 A，格式识别失败")

    df.columns = [str(c).strip() for c in df.columns]
    df = df.replace(["NULL", "null", "Null"], np.nan)

    out = pd.DataFrame()
    col_map = {
        "prod_desc": "prod_desc",
        "normal_price": "normal_price",
        "unit_dimension": "unit_dimension",
        "unit_number": "unit_number",
        "vendor_name": "vendor_name"
    }
    
    for target_col, src_col in col_map.items():
        if src_col in df.columns:
            out[target_col] = df[src_col]
        else:
            out[target_col] = np.nan

    out["prod_desc"] = out["prod_desc"].fillna("未知商品")
    out["normal_price"] = out["normal_price"].fillna("0")
    out["unit_dimension"] = out["unit_dimension"].fillna("个")
    
    out["unit_number"] = out["unit_number"].fillna("1")
    out["unit_number"] = out["unit_number"].apply(lambda x: "1" if str(x).strip() in ["0", ""] else x)
    
    out["vendor_name"] = out["vendor_name"].fillna("未知供货商")

    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    return out

# 第三部分：清洗B类文件 
def clean_b_specific(raw_csv_path: str, out_csv_path: str) -> pd.DataFrame:
    """针对 B.csv 的专门清洗逻辑"""
    print(f"   正在读取并清洗 B类文件: {raw_csv_path} ...")
    
    df = None
    for enc in ["utf-8", "gbk", "gb18030", "utf-8-sig"]:
        try:
            df = pd.read_csv(raw_csv_path, encoding=enc, dtype=str)
            break
        except:
            continue
            
    if df is None:
        raise ValueError("无法读取文件 B，编码识别失败")

    df.columns = [str(c).strip() for c in df.columns]
    df = df.replace(["NULL", "null", "Null"], np.nan)

    out = pd.DataFrame()
    
    if "prod_desc" in df.columns: out["prod_desc"] = df["prod_desc"]
    else: out["prod_desc"] = "未知商品"

    out["normal_price"] = "0"

    if "unit_dimension" in df.columns: out["unit_dimension"] = df["unit_dimension"]
    else: out["unit_dimension"] = "个"
    
    if "unit_number" in df.columns: out["unit_number"] = df["unit_number"]
    else: out["unit_number"] = "1"
        
    if "vendor_name" in df.columns: out["vendor_name"] = df["vendor_name"]
    else: out["vendor_name"] = "未知供货商"

    out["prod_desc"] = out["prod_desc"].fillna("")
    out["unit_dimension"] = out["unit_dimension"].fillna("个")
    out["unit_number"] = out["unit_number"].fillna("1")
    out["vendor_name"] = out["vendor_name"].fillna("未知供货商")

    out.to_csv(out_csv_path, index=False, encoding="utf-8-sig")
    return out

# 第四部分：清洗C类文件 
def fix_mojibake_specific(text: str) -> str:
    """C类专用：特定乱码修复逻辑"""
    if text is None:
        return ""
    s = str(text)

    for enc in ("gb18030", "gbk"):
        try:
            repaired = s.encode(enc, errors="ignore").decode("utf-8", errors="ignore")
            if repaired and repaired != s:
                s = repaired
                break
        except Exception:
            pass

    # 清理字符
    s = re.sub(r"[\ue000-\uf8ff]", "", s)
    s = s.replace("\u3000", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace("饮?", "饮料").replace("飲?", "饮料")
    s = s.replace("?", "")
    return s

def build_prod_desc(row: pd.Series) -> str:
    desc = fix_mojibake_specific(row.get(7, ""))
    vendor_hint = fix_mojibake_specific(row.get(12, ""))

    if not is_empty(vendor_hint) and not is_empty(desc):
        if not desc.startswith(vendor_hint):
            desc = vendor_hint + desc
    elif is_empty(desc) and not is_empty(vendor_hint):
        desc = vendor_hint

    desc = desc.replace("濢浪", "激浪")
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc

def format_price_clean(x: str) -> str:
    if is_empty(x):
        return ""
    s = str(x).strip()
    try:
        return str(float(s))
    except Exception:
        return s

def unit_dimension_rule(prod_desc: str, row: pd.Series) -> str:
    s = "" if prod_desc is None else str(prod_desc)

    if re.search(r"(\*|x|X|连|組|组|箱|提|打|套)", s):
        return "个"
    if re.search(r"\d+(\.\d+)?\s*L\b", s):
        return "个"

    m = re.search(r"(\d+(?:\.\d+)?)\s*ml\b", s, flags=re.I)
    if m:
        try:
            if float(m.group(1)) >= 1000:
                return "个"
        except Exception:
            pass

    raw21 = str(row.get(21, ""))
    raw20 = str(row.get(20, ""))
    if raw21.startswith("鐡") or ("鐡" in raw20):
        return "个"
    if raw21.startswith("鍚") or ("鍚" in raw20):
        return "瓶"

    return "瓶"

def vendor_name_rule(prod_desc: str) -> str:
    if prod_desc is None:
        return "未知供货商"
    s = str(prod_desc).strip()
    if s == "":
        return "未知供货商"
    if s.startswith("闆ⅶ"):
        return "未知供货商"

    if "牌" in s:
        name = s.split("牌", 1)[0].strip()
        name = re.sub(r"[\*\(\)（）\-\s]+", "", name)
        if len(name) >= 2:
            return name[:6]
        return "未知供货商"

    m = re.search(r"[0-9]", s)
    if m:
        s = s[:m.start()]
    s = re.sub(r"[\*\(\)（）\-\s]+", "", s)
    s = s[:6]
    return s if len(s) >= 2 else "未知供货商"

def run_cleaning_task(raw_csv_path: str, out_csv_path: str) -> pd.DataFrame:
    """执行 C 文件的清洗任务 (原通用逻辑)"""
    print(f"   正在读取并清洗 C类文件: {raw_csv_path} ...")
    raw = read_raw_csv_for_clean(raw_csv_path)
    raw = ensure_columns(raw, needed_max_col_index=21)
    out = pd.DataFrame()

    out["prod_desc"] = raw.apply(build_prod_desc, axis=1)
    out["normal_price"] = raw[10].apply(format_price_clean)
    out["unit_dimension"] = [
        unit_dimension_rule(out.loc[i, "prod_desc"], raw.loc[i])
        for i in range(len(raw))
    ]
    out["unit_number"] = "1"
    out["vendor_name"] = out["prod_desc"].apply(vendor_name_rule)

    out.to_csv(out_csv_path, index=False, encoding="utf-8-sig")
    return out

# 第五部分：清洗D类文件 
def _d_normalize_number_str(x) -> str:
    """D类专用：把数字字段标准化为字符串"""
    if is_empty(x):
        return ""
    s = str(x).strip()

    # 纯数字或小数
    if re.fullmatch(r"\d+(\.\d+)?", s):
        # 去掉 .0
        if s.endswith(".0"):
            s = s[:-2]
        return s

    # 尝试 float
    try:
        f = float(s)
        # 整数就转整数
        if abs(f - int(f)) < 1e-12:
            return str(int(f))
        return str(f)
    except Exception:
        return ""

def _d_fix_text(text: str) -> str:
    """D类专用：文本修复"""
    if text is None:
        return ""
    s = str(text)

    # 尝试逆转编码
    for enc in ("gb18030", "gbk"):
        try:
            repaired = s.encode(enc, errors="ignore").decode("utf-8", errors="ignore")
            if repaired and repaired != s:
                s = repaired
                break
        except Exception:
            pass

    # 清理
    s = re.sub(r"[\ue000-\uf8ff]", "", s) 
    s = s.replace("\u3000", " ")         
    s = re.sub(r"\s+", " ", s).strip()    
    s = s.replace("?", "")               

    return s

def _d_clean_prod_desc(x: str) -> str:
    """D类专用：生成 prod_desc (来自 col 4)"""
    s = _d_fix_text(x)
    s = s.replace("NULL", "").strip()

    if len(s) < 4:
        return "国产普烟"
    if s.endswith("(") or s.endswith("（"):
        return "国产普烟"
    return s

def _d_clean_price(x: str) -> str:
    """D类专用：normal_price (来自 col 6)"""
    if is_empty(x):
        return ""
    s = str(x).strip()
    if s.upper() == "NULL" or s == "":
        return ""
    try:
        return str(float(s))
    except Exception:
        return s

def _d_infer_unit_number(row: pd.Series) -> str:
    """D类专用：unit_number (优先 col 7, 9, 6)"""
    for col in (7, 9, 6):
        if col in row.index:
            v = _d_normalize_number_str(row.get(col, ""))
            if v != "":
                return v
    return ""

def _d_infer_unit_dimension(prod_desc: str) -> str:
    """D类专用：unit_dimension (支/个)"""
    s = "" if prod_desc is None else str(prod_desc)
    if re.search(r"(细支|\d+支|支全叶|支装)", s):
        return "支"
    return "个"

def _d_clean_vendor_name(row: pd.Series) -> str:
    """D类专用：vendor_name (从 cols 17-23 抓取)"""
    candidate_cols = [17, 18, 19, 20, 21, 22, 23]
    candidates = []

    for c in candidate_cols:
        if c not in row.index:
            continue
        raw_val = row.get(c, "")
        if is_empty(raw_val):
            continue

        raw_val_str = str(raw_val).strip()

        # 跳过文件名或明显无关字段
        if "XTD_product_" in raw_val_str or raw_val_str.lower().endswith(".csv"):
            continue
        if raw_val_str in ("1*10", "1*20", "1*50"):
            continue

        txt = _d_fix_text(raw_val_str)

        # 只收集“像公司名”的
        if ("公司" in txt) or ("烟草" in txt):
            candidates.append(txt)

    if not candidates:
        return "未知供货商"

    v = candidates[0]
    if "烟草公" in v and "烟草公司" not in v:
        v = v.replace("烟草公", "烟草公司")
    v = re.sub(r"\d+$", "", v)
    v = v.replace(")", "").replace("）", "")
    v = re.sub(r"\s+", "", v).strip()

    return v if v else "未知供货商"

def clean_d_specific(raw_csv_path: str, out_csv_path: str) -> pd.DataFrame:
    """针对 D.csv 的专门清洗逻辑 (整合自 qingxi2.py)"""
    print(f"   正在读取并清洗 D类文件: {raw_csv_path} ...")
    
    raw = read_raw_csv_for_clean(raw_csv_path)
    
    # D类文件常见有 24 列；确保至少到 23
    raw = ensure_columns(raw, needed_max_col_index=23)
    
    # 如果第一行完全空，删掉
    if not raw.empty:
        first_row_all_empty = raw.iloc[0].astype(str).str.strip().eq("").all()
        if first_row_all_empty:
            raw = raw.iloc[1:].reset_index(drop=True)

    out = pd.DataFrame()

    # prod_desc：来自 col4
    out["prod_desc"] = raw[4].apply(_d_clean_prod_desc)

    # normal_price：来自 col6
    out["normal_price"] = raw[6].apply(_d_clean_price)

    # unit_number：优先 col7，其次 col9，再次 col6
    out["unit_number"] = raw.apply(_d_infer_unit_number, axis=1)

    # unit_dimension：从 prod_desc 推断（支/个）
    out["unit_dimension"] = out["prod_desc"].apply(_d_infer_unit_dimension)

    # vendor_name：从漂移列中抓“公司/烟草”
    out["vendor_name"] = raw.apply(_d_clean_vendor_name, axis=1)

    # 确保列顺序
    out = out[["prod_desc", "normal_price", "unit_dimension", "unit_number", "vendor_name"]]

    out.to_csv(out_csv_path, index=False, encoding="utf-8-sig")
    return out


# 第六部分：客户端工具 

SERVER_IP = "127.0.0.1"
UDP_PORT = 9000
TCP_PORT = 9001

def safe_int(x, default=1):
    try:
        if x is None: return default
        s = str(x).strip()
        if s == "" or s.lower() in ("nan", "none", "null"): return default
        m = re.findall(r"\d+", s)
        v = int(m[0]) if m else default
        return v if v > 0 else default
    except:
        return default

def safe_float(x, default=0.0):
    try:
        if x is None: return default
        s = str(x).strip()
        if s == "" or s.lower() in ("nan", "none", "null"): return default
        s = s.replace(",", "")
        m = re.findall(r"-?\d+(?:\.\d+)?", s)
        return float(m[0]) if m else default
    except:
        return default

def read_table_smart(path: str) -> pd.DataFrame:
    # 优先读取 Excel
    if path.lower().endswith(".xlsx") or path.lower().endswith(".xls"):
        try:
            return pd.read_excel(path, dtype=str)
        except:
            pass 

    # 尝试多种 CSV 编码
    for enc in ["utf-8-sig", "utf-8", "gb18030", "gbk"]:
        try:
            df = pd.read_csv(path, encoding=enc, header="infer", engine="python", dtype=str)
            if "prod_desc" in df.columns:
                return df 
            return df
        except Exception:
            continue
            
    # 无头读取兜底
    try:
        df = pd.read_csv(path, header=None, engine="python", dtype=str, encoding="utf-8-sig")
        df.columns = [f"col_{i}" for i in range(df.shape[1])]
        return df
    except Exception as e:
        raise e

def auto_detect_columns(df: pd.DataFrame):
    """自动识别列名，兼容清洗后文件和原始文件"""
    cols = list(df.columns)
    col_map = {}
    
    # 1. 优先完全匹配（清洗后的文件必然命中）
    if "prod_desc" in cols: col_map["prod_desc"] = "prod_desc"
    if "normal_price" in cols: col_map["normal_price"] = "normal_price"
    if "unit_dimension" in cols: col_map["unit_dimension"] = "unit_dimension"
    if "unit_number" in cols: col_map["unit_number"] = "unit_number"
    if "vendor_name" in cols: col_map["vendor_name"] = "vendor_name"
    
    if len(col_map) >= 4:
        return col_map

    # 2. 模糊匹配 (兼容未清洗文件)
    def _col_score(col_name, field):
        name = str(col_name).lower().strip()
        score = 0
        if field == "prod_desc":
            if any(k in name for k in ["desc", "name", "品名", "商品", "描述"]): score += 10
        elif field == "normal_price":
            if any(k in name for k in ["price", "价格", "单价", "金额"]): score += 10
        elif field == "unit_dimension":
            if any(k in name for k in ["unit", "dimension", "规格", "单位"]): score += 10
        elif field == "unit_number":
            if any(k in name for k in ["qty", "quantity", "num", "数量", "件数"]): score += 10
        elif field == "vendor_name":
            if any(k in name for k in ["vendor", "supplier", "供货", "供应"]): score += 10
        return score

    for field in ["prod_desc", "normal_price", "unit_dimension", "unit_number", "vendor_name"]:
        if field not in col_map:
            best_col = max(cols, key=lambda c: _col_score(c, field))
            if _col_score(best_col, field) > 0:
                col_map[field] = best_col
                
    return col_map

def parse_file(fname: str) -> pd.DataFrame:
    df = read_table_smart(fname)
    col_map = auto_detect_columns(df)
    
    out = pd.DataFrame()
    
    if "prod_desc" in col_map: out["prod_desc"] = df[col_map["prod_desc"]]
    else: out["prod_desc"] = "未知商品"
        
    if "normal_price" in col_map: out["normal_price"] = df[col_map["normal_price"]]
    else: out["normal_price"] = "0"
        
    if "unit_dimension" in col_map: out["unit_dimension"] = df[col_map["unit_dimension"]]
    else: out["unit_dimension"] = "个"
        
    if "unit_number" in col_map: out["unit_number"] = df[col_map["unit_number"]]
    else: out["unit_number"] = "1"
        
    if "vendor_name" in col_map: out["vendor_name"] = df[col_map["vendor_name"]]
    else: out["vendor_name"] = "未知供货商"
    
    out["unit_number"] = out["unit_number"].apply(lambda x: safe_int(x, default=1))
    out["normal_price"] = out["normal_price"].apply(lambda x: safe_float(x, default=0.0))
    out["vendor_name"] = out["vendor_name"].fillna("未知供货商").astype(str)
    
    return out


# 第七部分：主流程 (Main)
if __name__ == "__main__":
    
    print("=" * 60)
    print("第一阶段：自动数据清洗")
    print("=" * 60)
    
    # 待处理文件列表
    files_to_process = [
        ("A.xlsx", "A.clean.csv"),
        ("B.csv", "B.clean.csv"),
        ("C.csv", "C.clean.csv"),
        ("D.csv", "D.clean.csv"),
    ]
    
    cleaned_files_exist = []

    for input_file, output_file in files_to_process:
        if os.path.exists(input_file):
            try:
                print(f"📄 发现源文件 {input_file}，开始清洗...")
                
                # 分发不同的清洗逻辑 (顺序 A -> B -> C -> D)
                if input_file.startswith("A."):
                    df_clean = clean_a_specific(input_file, output_file)
                    
                elif input_file.startswith("B."):
                    df_clean = clean_b_specific(input_file, output_file)
                    
                elif input_file.startswith("C."):
                    df_clean = run_cleaning_task(input_file, output_file)
                    
                elif input_file.startswith("D."):
                    df_clean = clean_d_specific(input_file, output_file)
                    
                else:
                    # 兜底情况，默认尝试用C类的强力清洗逻辑
                    df_clean = run_cleaning_task(input_file, output_file)
                    
                print(f"✅ 清洗成功: {output_file} (行数: {len(df_clean)})")
                cleaned_files_exist.append(output_file)
            except Exception as e:
                print(f"❌ 清洗失败 {input_file}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️ 未找到源文件 {input_file}，跳过清洗")
            
    print("\n" + "=" * 60)
    print("第二阶段：客户端数据预览与发送")
    print("=" * 60)

    display_files = cleaned_files_exist
    
    if not display_files:
        print("没有可用的清洗后文件。")
        exit(1)
    
    # 预览
    print("\n📊 可选发送文件列表：")
    for f in display_files:
        if os.path.exists(f):
            try:
                df0 = read_table_smart(f)
                print(f"  • {f:<15} 列数: {len(df0.columns)} | 前3行: {df0.iloc[0].tolist() if not df0.empty else '空'}")
            except:
                print(f"  • {f:<15} (读取失败)")

    print("-" * 60)

    # UDP 握手
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        udp.sendto("数据传输请求".encode("utf-8"), (SERVER_IP, UDP_PORT))
        msg, _ = udp.recvfrom(1024)
        print(f"📡 服务端响应: {msg.decode('utf-8', errors='ignore')}")
    except Exception as e:
        print("❌ 无法连接到服务端 (UDP握手失败)，请确认 server.py 已运行。")
    
    mode = input("\n请输入通信方式（1=TCP，0=UDP）：").strip()
    try:
        udp.sendto(mode.encode("utf-8"), (SERVER_IP, UDP_PORT))
        msg, _ = udp.recvfrom(1024)
        print(f"📡 服务端确认: {msg.decode('utf-8', errors='ignore')}")
    except:
        pass

    # 选择文件
    files_str = " ".join(display_files)
    filename = input(f"请输入要发送的文件名（例如 {files_str}）：").strip()

    if not os.path.exists(filename):
        print("❌ 文件不存在，程序退出")
        exit(1)

    # 根据文件名首字母作为门店代号
    shop_code = filename[0].upper()
    
    # 解析并转换为标准格式
    print(f"\n正在解析文件 {filename} ...")
    df_to_send = parse_file(filename)
    print("✅ 解析完成，发送数据预览：")
    print(df_to_send.head())
    
    # 发送循环
    start_time = time.time()
    
    if mode == "1":
        # TCP
        try:
            tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp.connect((SERVER_IP, TCP_PORT))
            print("\n🚀 开始 TCP 传输...")

            for _, row in df_to_send.iterrows():
                payload = {
                    "retailler": shop_code,
                    "prod_desc": str(row["prod_desc"]),
                    "price": float(row["normal_price"]),
                    "unit": str(row["unit_dimension"]),
                    "quantity": int(row["unit_number"]),
                    "vendor": str(row["vendor_name"])
                }
                json_str = json.dumps(payload, ensure_ascii=False)
                full_msg = json_str + "\n"
                tcp.sendall(full_msg.encode("utf-8"))
            
            tcp.sendall("信息传输结束，我将断开连接".encode("utf-8"))
            tcp.close()
            print("✅ TCP 传输完成")

        except ConnectionResetError:
            print("❌ TCP 连接被服务端强制断开")
        except Exception as e:
            print(f"❌ TCP 异常: {e}")

    else:
        # UDP
        try:
            print("\n🚀 开始 UDP 传输...")
            for _, row in df_to_send.iterrows():
                payload = {
                    "retailler": shop_code,
                    "prod_desc": str(row["prod_desc"]),
                    "price": float(row["normal_price"]),
                    "unit": str(row["unit_dimension"]),
                    "quantity": int(row["unit_number"]),
                    "vendor": str(row["vendor_name"])
                }
                udp.sendto(json.dumps(payload, ensure_ascii=False).encode("utf-8"), (SERVER_IP, UDP_PORT))

            udp.sendto("信息传输结束，我将断开连接".encode("utf-8"), (SERVER_IP, UDP_PORT))
            print("✅ UDP 传输完成")
            
        except Exception as e:
            print(f"❌ UDP 异常: {e}")

    end_time = time.time()
    print(f"\n任务耗时: {end_time - start_time:.4f} 秒")


# In[ ]:




