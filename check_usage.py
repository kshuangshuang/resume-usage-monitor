# -*- coding: utf-8 -*-
"""ResumeSDK 剩余用量监控脚本

功能：登录 ResumeSDK 查询页面，解析剩余用量，低于阈值时发送邮件提醒。
运行方式：本地 python check_usage.py 或 GitHub Actions 定时触发。

环境变量（GitHub Secrets 中配置）：
  - RESUME_SDK_UID: ResumeSDK 用户名
  - RESUME_SDK_PWD: ResumeSDK 密码
  - SMTP_USER: 发件邮箱地址（QQ邮箱）
  - SMTP_PASS: QQ邮箱授权码（非QQ密码）
  - ALERT_TO: 收件邮箱地址
"""

import os
import re
import html
import smtplib
import requests
from email.mime.text import MIMEText

# ---- 配置 ----
QUERY_URL = "https://resumesdk.com/api/query_user"
THRESHOLD = 25000  # 剩余用量阈值，低于此值发送提醒


def query_remaining_usage(uid: str, pwd: str) -> dict:
    """查询 ResumeSDK 账户用量信息

    页面行为：POST 提交后返回完整 HTML，结果在 id="res_div" 的 div 中，
    内容为 HTML 编码格式（&lt; &gt;），解码后格式：
    用户<2112010>: 创建日期<...>,总用量<2131000>,剩余用量<25147>

    Args:
        uid: 用户名
        pwd: 密码

    Returns:
        dict: 包含 total(总用量) 和 remaining(剩余用量) 的字典
    """
    # 先 GET 页面获取 session cookie，再 POST 提交查询
    session = requests.Session()
    session.get(QUERY_URL, timeout=30)
    resp = session.post(QUERY_URL, data={"uid": uid, "pwd": pwd}, timeout=30)
    resp.raise_for_status()

    # 从 HTML 中提取 res_div 内容
    match = re.search(r'id="res_div"[^>]*>(.*?)</div>', resp.text, re.DOTALL)
    if not match:
        raise ValueError(f"响应中未找到 res_div 内容")

    # HTML 解码（&lt; → <, &gt; → >）
    text = html.unescape(match.group(1).strip())
    print(f"查询结果: {text}")

    # 解析格式：用户<2112010>: 创建日期<...>,总用量<2131000>,剩余用量<25147>
    remaining_match = re.search(r"剩余用量<(\d+)>", text)
    total_match = re.search(r"总用量<(\d+)>", text)

    if not remaining_match:
        raise ValueError(f"无法从响应中解析剩余用量: {text}")

    return {
        "total": int(total_match.group(1)) if total_match else 0,
        "remaining": int(remaining_match.group(1)),
        "raw": text,
    }


def send_alert_email(smtp_user: str, smtp_pass: str, to_addr: str, remaining: int, total: int):
    """发送剩余用量不足的告警邮件

    Args:
        smtp_user: 发件邮箱
        smtp_pass: 邮箱授权码
        to_addr: 收件邮箱
        remaining: 剩余用量
        total: 总用量
    """
    subject = f"[ResumeSDK告警] 剩余用量不足: {remaining}"
    body = (
        f"ResumeSDK 简历解析服务剩余用量不足！\n\n"
        f"总用量: {total}\n"
        f"剩余用量: {remaining}\n"
        f"阈值: {THRESHOLD}\n\n"
        f"请及时充值，避免业务中断。"
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = smtp_user
    msg["To"] = to_addr  # 多个收件人用逗号分隔
    msg["Subject"] = subject

    # QQ邮箱 SMTP 服务器
    with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=30) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_addr.split(","), msg.as_string())

    print(f"告警邮件已发送至 {to_addr}")


def main():
    # 从环境变量读取配置
    uid = os.environ.get("RESUME_SDK_UID", "2112010")
    pwd = os.environ.get("RESUME_SDK_PWD", "")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    alert_to = os.environ.get("ALERT_TO", "2667362660@qq.com,kanshuangshuang@h-y-y.com")

    if not pwd:
        print("错误: 未设置 RESUME_SDK_PWD 环境变量")
        return

    # 查询用量
    try:
        info = query_remaining_usage(uid, pwd)
    except (requests.RequestException, ValueError) as e:
        print(f"查询失败: {e}")
        return

    remaining = info["remaining"]
    total = info["total"]
    print(f"总用量: {total}, 剩余用量: {remaining}, 阈值: {THRESHOLD}")

    # 判断是否需要告警
    if remaining <= THRESHOLD:
        if not smtp_user or not smtp_pass:
            print(f"剩余用量 {remaining} 已低于阈值 {THRESHOLD}，但未配置邮箱，无法发送告警")
            return

        try:
            send_alert_email(smtp_user, smtp_pass, alert_to, remaining, total)
        except Exception as e:
            print(f"邮件发送失败: {e}")
    else:
        print(f"剩余用量充足，无需告警")


if __name__ == "__main__":
    main()
