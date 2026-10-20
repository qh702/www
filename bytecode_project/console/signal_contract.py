"""Static contract extracted from the supplied Signal 8.30.3 APK.

This file centralizes APK/version/UI facts used by the recovery overlays so
future APK updates can be diffed without scattering literals across modules.
"""

APK_SHA256 = "FC57AF9D545C232E583D106D56181250342479635D693CAE86A1C2751244CD63"
PACKAGE = "org.thoughtcrime.securesms"
VERSION_NAME = "8.30.3"
VERSION_CODE = 176301
MIN_SDK = 23
TARGET_SDK = 36

LAUNCHER_ACTIVITY = "org.thoughtcrime.securesms.RoutingActivity"
REGISTRATION_ACTIVITY = "org.signal.registration.RegistrationActivity"
REGISTRATION_ACTIVITY_EXPORTED = False

CAPTCHA_PAGE_URL = "https://signalcaptchas.org/registration/generate.html"
CAPTCHA_CALLBACK_SCHEME = "signalcaptcha://"
CAPTCHA_CALLBACK_PREFIX_LENGTH = 16
CAPTCHA_CALLBACK_EXPORTED = False

# Registration controller methods found in DEX.  These are internal app
# contracts, not public HTTP endpoints.
REGISTRATION_CONTROLLER_METHODS = (
    "createSession",
    "getSession",
    "requestVerificationCode",
    "getCaptchaUrl",
    "registerAccount",
    "setProfile",
    "setPinAndMasterKeyOnSvr",
    "getRemoteBackupInfo",
    "setRestoreMethod",
)

BACKUP_PAGE_MARKERS = frozenset(
    {
        "還原或轉移帳戶",
        "还原或转移帐户",
        "選擇要還原訊息紀錄和帳戶資料的方式。",
        "选择要还原消息记录和帐户数据的方式。",
        "Restore or transfer account",
    }
)

BACKUP_SKIP_LABELS = frozenset(
    {
        "不轉移並繼續",
        "不转移并继续",
        "Continue without transferring",
        "Skip transfer and continue",
    }
)
