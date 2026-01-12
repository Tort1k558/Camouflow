import asyncio
import random
import string
from typing import Dict, List, Optional

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.core.browser_interface import BrowserInterface


class StageAds(BrowserInterface):
    def __init__(
        self,
        login: str,
        password: str,
        auth2: str,
        proxy: str,
        ads_url: str,
        video_headline: str,
        video_description: str,
        keep_browser_open: bool = True,
        profile_name: Optional[str] = None,
    ):
        super().__init__(login, password, auth2, proxy, keep_browser_open, profile_name=profile_name)
        self.ads_url = ads_url
        self.video_headline = video_headline
        self.video_description = video_description

    async def _type(self, selector: str, value: str, click: bool = True):
        el = await self.page.wait_for_selector(selector, timeout=60000)
        if click:
            await el.click()
        await self._human_type(el, value, clear=True)

    async def _click(self, selector: str, timeout: int = 60000):
        el = await self.page.wait_for_selector(selector, timeout=timeout)
        await el.click()

    async def run_stage(self) -> bool:
        try:
            await self.page.goto("https://ads.google.com", wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_load_state("networkidle", timeout=60000)

            self.logger.info("Click start ADS button")
            await self._click('xpath=/html/body/header/div[2]/section/div/div[1]/div[3]/a[2]')
            rand_name = "".join(random.choices(string.ascii_lowercase, k=random.randint(5, 10)))
            self.logger.info("Typing company name")
            await self._type(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div[1]/account-onboarding-root/div/div/view-loader/business-root/div[1]/left-stepper/div[1]/div[1]/div[1]/left-stepper-content/dynamic-component/business-name-wrapper/div/div/business-name-view-for-chat/div/div[1]/material-input/div/div[1]/label/input',
                rand_name,
            )
            self.logger.info("Typing ads url")
            await self._type(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div[1]/account-onboarding-root/div/div/view-loader/business-root/div[1]/left-stepper/div[1]/div[1]/div[1]/left-stepper-content/dynamic-component/business-name-wrapper/div/div/business-name-view-for-chat/div/div[2]/material-radio-group/material-radio[1]/div[2]/div/div[2]/div/material-input/div[1]/div[1]/label/input',
                self.ads_url,
            )
            self.logger.info("Click next")
            await self._click(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div[1]/account-onboarding-root/div/div/view-loader/business-root/div[1]/left-stepper/div[1]/div[1]/div[1]/left-stepper-content/dynamic-component/business-name-wrapper/div/div/div/button-panel/div/div/material-button/div[1]'
            )
            self.logger.info("Click skip")
            await self._click(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div[1]/account-onboarding-root/div/div/view-loader/business-root/div[1]/left-stepper/div[1]/div[1]/div[2]/left-stepper-content/dynamic-component/linking-wrapper/div/button-panel/div/div/material-button[3]/div[1]'
            )
            self.logger.info("Click skip")
            await self._click(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div[1]/account-onboarding-root/div/div/view-loader/business-root/div[1]/left-stepper/div[1]/div[1]/div[3]/left-stepper-content/dynamic-component/campaign-goals-wrapper/div/button-panel/div/div/material-button[3]/div[1]'
            )

            self.logger.info("Click campaign type video")
            await self._click(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div[1]/account-onboarding-root/div/div/view-loader/business-root/div[1]/left-stepper/div[1]/div[1]/div[4]/left-stepper-content/dynamic-component/campaign-type-wrapper/div/campaign-type-view/div/div/campaign-type-picker/div[2]/channel-selection-card/div/div/material-radio/div[1]'
            )
            self.logger.info("Click next")
            await self._click(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div[1]/account-onboarding-root/div/div/view-loader/business-root/div[1]/left-stepper/div[1]/div[1]/div[4]/left-stepper-content/dynamic-component/campaign-type-wrapper/div/button-panel/div/div/material-button[1]/div[1]'
            )

            self.logger.info("Click type of budget waste")
            await self._click(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div[4]/video-root/construction-base-root/view-loader/video-campaign-construction-shell/video-campaign-construction/left-stepper/div[1]/div[1]/div[1]/left-stepper-content/dynamic-component/campaign-construction-section/section/campaign-construction-panel/budget-and-dates/expansion-panel/material-expansionpanel/div/div[2]/div/div[1]/div/div/div/section/div/div[2]/div[1]/material-dropdown-select/dropdown-button'
            )


            self.logger.info("Click type of budget waste daily")
            await self._click(
                'xpath=/html/body/div[8]/div[28]/div/div/div[2]/div[2]/material-list/div/div/material-select-dropdown-item'
            )

            self.logger.info("Typing amount of budget waste")
            await self._type(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div[4]/video-root/construction-base-root/view-loader/video-campaign-construction-shell/video-campaign-construction/left-stepper/div[1]/div[1]/div[1]/left-stepper-content/dynamic-component/campaign-construction-section/section/campaign-construction-panel/budget-and-dates/expansion-panel/material-expansionpanel/div/div[2]/div/div[1]/div/div/div/section/div/div[2]/div[2]/money-input/mask-money-input/material-input/div[1]/div[1]/label/input',
                "10.12",
            )

            self.logger.info("Click no political")
            await self._click(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div[4]/video-root/construction-base-root/view-loader/video-campaign-construction-shell/video-campaign-construction/left-stepper/div[1]/div[1]/div[1]/left-stepper-content/dynamic-component/campaign-construction-section/section/campaign-construction-panel/eu-political-ads-panel/expansion-panel/material-expansionpanel/div/div[2]/div/div[1]/div/div/div/div/div/eu-political-ads/div/div/material-radio-group/material-radio[2]'
            )


            self.logger.info("Typing add video url")
            await self._type(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div[4]/video-root/construction-base-root/view-loader/video-campaign-construction-shell/video-campaign-construction/left-stepper/div[1]/div[1]/div[3]/left-stepper-content/dynamic-component/ads-construction-section/section/multi-ad-construction-panel/ad-construction-subpanel/div/div/ad-construction-panel/div/div/div[1]/multi-video-picker/video-picker/div/div/material-auto-suggest-input/material-input/div[1]/div[1]/label/input',
                self.ads_url,
            )

            self.logger.info("Typing add main video url")
            await self._type(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div/video-root/construction-base-root/view-loader/video-campaign-construction-shell/video-campaign-construction/left-stepper/div[1]/div[1]/div[3]/left-stepper-content/dynamic-component/ads-construction-section/section/multi-ad-construction-panel/ad-construction-subpanel/div/div/ad-construction-panel/div/div/div[1]/div[7]/div[1]/format-agnostic-panel/url-input/div/div/div/material-input/div[1]/div[1]/label/input',
                self.ads_url,
            )

            self.logger.info("Typing video headline")
            await self._type(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div/video-root/construction-base-root/view-loader/video-campaign-construction-shell/video-campaign-construction/left-stepper/div[1]/div[1]/div[3]/left-stepper-content/dynamic-component/ads-construction-section/section/multi-ad-construction-panel/ad-construction-subpanel/div/div/ad-construction-panel/div/div/div[1]/div[7]/div[1]/format-agnostic-panel/multi-asset-editor[1]/div/div/material-auto-suggest-input/material-input/div[1]/div[1]/label/input',
                self.video_headline,
            )
            
            self.logger.info("Typing video description")
            await self._type(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div/video-root/construction-base-root/view-loader/video-campaign-construction-shell/video-campaign-construction/left-stepper/div[1]/div[1]/div[3]/left-stepper-content/dynamic-component/ads-construction-section/section/multi-ad-construction-panel/ad-construction-subpanel/div/div/ad-construction-panel/div/div/div[1]/div[7]/div[1]/format-agnostic-panel/multi-asset-editor[2]/div/div/material-auto-suggest-input/material-input/div[1]/div[1]/label/input',
                self.video_description,
            )

            self.logger.info("Click apply cpv bid")
            await self._click(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div/video-root/construction-base-root/view-loader/video-campaign-construction-shell/video-campaign-construction/left-stepper/div[1]/div[1]/div[4]/left-stepper-content/dynamic-component/bid-construction-section/section/bid-input/expansion-panel/material-expansionpanel/div/div[2]/div/div[1]/div/div/div/section/div/div/div[2]/bid-suggestion/loading-container/div/div/callout/div/div/div/button'
            )

            self.logger.info("Click create campaign")
            await self._click(
                'xpath=/html/body/div[1]/root/div/div[1]/div[2]/div/div[3]/div/div/awsm-child-content/content-main/div/div[4]/video-root/construction-base-root/view-loader/video-campaign-construction-shell/video-campaign-construction/left-stepper/div[1]/div[1]/save-cancel-buttons/div/material-yes-no-buttons/material-button[1]'
            )
            return True
        except PlaywrightTimeoutError:
            return False
        except Exception:
            return False


def run_ads_stage(
    accounts: List[Dict],
    max_accounts: int,
    ads_url: str,
    video_headline: str,
    video_description: str,
) -> List[Dict]:
    to_run = accounts[:max_accounts]

    async def runner() -> List[Dict]:
        processed: List[Dict] = []
        for acc in to_run:
            proxy = ""
            host = acc.get("proxy_host")
            port = acc.get("proxy_port")
            user = acc.get("proxy_user")
            pwd = acc.get("proxy_password")
            if host and port:
                if user and pwd:
                    proxy = f"socks5://{host}:{port}:{user}:{pwd}"
                else:
                    proxy = f"socks5://{host}:{port}"
            stage = StageAds(
                login=str(acc.get("email") or ""),
                password=str(acc.get("password") or ""),
                auth2=str(acc.get("twofa_url") or ""),
                proxy=proxy,
                ads_url=ads_url,
                video_headline=video_headline,
                video_description=video_description,
                keep_browser_open=True,
                profile_name=str(acc.get("name") or acc.get("email") or "profile"),
            )
            try:
                await stage.start()
                ok = await stage.run_stage()
                if ok:
                    processed.append(acc)
            except Exception:
                continue
        return processed

    return asyncio.run(runner())
