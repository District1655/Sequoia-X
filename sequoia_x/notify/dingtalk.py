"""钉钉通知模块：将选股结果通过 Webhook 推送至钉钉群机器人。"""

import base64
import hashlib
import hmac
import time
import urllib.parse
from datetime import date

import requests

from sequoia_x.core.config import Settings
from sequoia_x.core.logger import get_logger

logger = get_logger(__name__)


class DingTalkNotifier:
    """钉钉群机器人 Webhook 推送器。

    安全设置支持：
      - 加签（推荐）：配置 DINGTALK_SECRET，自动拼接 timestamp + sign
      - 自定义关键词：在钉钉机器人后台把关键词设为 "Sequoia"
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def _to_xueqiu_code(code: str) -> str:
        """将纯数字代码转为雪球格式：6开头→SH，4/8开头→BJ，其余→SZ。"""
        if code.startswith("6"):
            return f"SH{code}"
        elif code.startswith(("4", "8")):
            return f"BJ{code}"
        return f"SZ{code}"

    @staticmethod
    def _get_stock_names(symbols: list[str]) -> dict[str, str]:
        """通过 baostock 批量查询股票名称，返回 {code: name} 映射。"""
        import baostock as bs
        bs.login()
        mapping = {}
        for code in symbols:
            prefix = "sh" if code.startswith(("6", "9")) else "sz"
            rs = bs.query_stock_basic(code=f"{prefix}.{code}")
            while rs.next():
                row = rs.get_row_data()
                mapping[code] = row[1]
        bs.logout()
        return mapping

    @staticmethod
    def _sign_url(webhook: str, secret: str) -> str:
        """加签：拼接 timestamp 和 sign 到 webhook URL。"""
        if not secret:
            return webhook
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        sep = "&" if "?" in webhook else "?"
        return f"{webhook}{sep}timestamp={timestamp}&sign={sign}"

    def _build_markdown(self, symbols: list[str], strategy_name: str) -> dict:
        today = date.today().strftime("%Y-%m-%d")
        names = self._get_stock_names(symbols)

        lines: list[str] = []
        for code in symbols:
            xq_code = self._to_xueqiu_code(code)
            name = names.get(code, xq_code)
            lines.append(f"- [{name}](https://xueqiu.com/S/{xq_code})  `{code}`")
        symbol_text = "\n".join(lines) if lines else "（无选股结果）"

        text = (
            f"### 📈 Sequoia-X 选股播报\n\n"
            f"**日期：** {today}\n\n"
            f"**策略：** {strategy_name}\n\n"
            f"**数量：** {len(symbols)}\n\n"
            f"**选股列表：**\n\n{symbol_text}"
        )
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": f"📈 Sequoia-X | {strategy_name}",
                "text": text,
            },
        }

    def send(
        self,
        symbols: list[str],
        strategy_name: str,
        webhook_key: str = "default",
    ) -> None:
        """将选股结果格式化为钉钉 Markdown 消息并 POST。

        Args:
            symbols: 选股结果代码列表。
            strategy_name: 策略名称。
            webhook_key: 兼容飞书接口，钉钉暂忽略（所有策略推同一群）。
        """
        webhook = self.settings.dingtalk_webhook_url
        if not webhook:
            logger.error("钉钉推送失败：未配置 DINGTALK_WEBHOOK_URL")
            return

        url = self._sign_url(webhook, self.settings.dingtalk_secret)
        payload = self._build_markdown(symbols, strategy_name)

        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()
            if resp.status_code != 200 or data.get("errcode") != 0:
                logger.error(
                    f"钉钉推送失败 HTTP={resp.status_code} 响应={resp.text}"
                )
            else:
                logger.info(f"钉钉推送成功，共 {len(symbols)} 只股票")
        except requests.RequestException as exc:
            logger.error(f"钉钉推送请求异常：{exc}")
