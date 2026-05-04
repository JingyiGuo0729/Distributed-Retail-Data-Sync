#!/usr/bin/env python
# coding: utf-8

# In[1]:


import socket
import threading
import json
import time
import pandas as pd
from datetime import datetime
import os

UDP_PORT = 9000
TCP_PORT = 9001

service_data = {}   # { "A": [ {}, {}, ... ] }

# =================  保存 Excel =================
def save_to_excel():
    writer = pd.ExcelWriter("service.xlsx", engine="openpyxl")
    for shop, records in service_data.items():
        df = pd.DataFrame(records)
        df.to_excel(writer, sheet_name=shop, index=False)
    writer.close()
    print(" 数据已保存至 service.xlsx")

# =================  记录断开日志 =================
def save_log(shop, recv_time):
    with open(f"{shop}_disconnect_log.txt", "w", encoding="utf-8") as f:
        f.write(f"门店：{shop}\n")
        f.write(f"接收完成时间：{datetime.now()}\n")
        f.write(f"服务中心接收耗时：{recv_time:.4f} 秒\n")

# =================  TCP 接收线程 =================
def tcp_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
    s.bind(("", TCP_PORT))
    s.listen(1)
    print("TCP 服务器监听中...")

    conn, addr = s.accept()
    print("TCP 客户端连接：", addr)

    start_time = None
    buffer = ""  

    try:
        while True:
            data = conn.recv(4096)
            if not data: break 
            buffer += data.decode("utf-8")

            while "\n" in buffer:
                msg, buffer = buffer.split("\n", 1) 
                msg = msg.strip()
                
                if not msg: continue 

                if msg == "信息传输结束，我将断开连接":
                    end_time = time.time()
                    
                    if service_data: 
                        shop = list(service_data.keys())[-1]
                        save_log(shop, end_time - start_time)
                        save_to_excel()
                    return # 结束函数

                if start_time is None:
                    start_time = time.time()

                try:
                    record = json.loads(msg)
                    shop = record["retailler"]
                    service_data.setdefault(shop, []).append(record)
                except json.JSONDecodeError:
                    print(f"解析错误，跳过数据: {msg}")

    except Exception as e:
        print(f"TCP 连接异常: {e}")
    finally:
        conn.close()
# =================  UDP 主服务 =================
udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp.bind(("", UDP_PORT))
print(" UDP 服务已启动...")

while True:
    data, addr = udp.recvfrom(1024)
    msg = data.decode("utf-8")
    print("收到：", msg)

    if msg == "数据传输请求":
        udp.sendto("请选择数据传输方式：TCP=1，UDP=0".encode("utf-8"), addr)

        mode, _ = udp.recvfrom(1024)
        mode = mode.decode("utf-8")

        udp.sendto("我已准备完毕，请开始传输".encode("utf-8"), addr)

        # 选择 TCP
        if mode == "1":
            threading.Thread(target=tcp_server).start()

        # 选择 UDP
        else:
            start_time = None
            while True:
                data, _ = udp.recvfrom(4096)
                msg = data.decode("utf-8")

                if msg == "信息传输结束，我将断开连接":
                    end_time = time.time()
                    shop = list(service_data.keys())[-1]
                    save_log(shop, end_time - start_time)
                    save_to_excel()
                    break

                if start_time is None:
                    start_time = time.time()

                record = json.loads(msg)
                shop = record["retailler"]
                service_data.setdefault(shop, []).append(record)


# In[ ]:




