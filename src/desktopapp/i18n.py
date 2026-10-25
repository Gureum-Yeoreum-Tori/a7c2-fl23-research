"""Display-only localization. Worker actions and saved camera data stay verbatim."""
from PySide6 import QtCore, QtWidgets
from .ko import STRINGS

_language = 'zh_CN'


def tr(source):
    return STRINGS.get(source, source) if _language == 'ko' else source


class StandardButtons(QtCore.QTranslator):
    """Translate Qt's standard confirmation buttons as well as application text."""
    def isEmpty(self):
        return False

    def translate(self, context, source, disambiguation=None, n=-1):
        if _language != 'ko':
            return ''
        return {'&Yes': '예', '&No': '아니요', 'Yes': '예', 'No': '아니요',
                'OK': '확인', '&OK': '확인', 'Cancel': '취소', '&Cancel': '취소',
                'Close': '닫기', '&Close': '닫기', 'Open': '열기', '&Open': '열기',
                'Save': '저장', '&Save': '저장', 'Apply': '적용', 'Reset': '초기화',
                'Restore Defaults': '기본값 복원', 'Help': '도움말'}.get(source, '')


def configure(language):
    global _language
    _language = language if language in ('ko', 'zh_CN') else 'ko'
    app = QtWidgets.QApplication.instance()
    if app is not None:
        previous = getattr(app, '_interface_translator', None)
        if previous is not None:
            app.removeTranslator(previous)
        app._interface_translator = StandardButtons(app)
        app.installTranslator(app._interface_translator)
    return _language
