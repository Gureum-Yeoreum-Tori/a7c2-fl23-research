"""Language persistence and identical GUI dispatch, with physical USB blocked."""
import ast
import json
import os
from pathlib import Path
import re
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6 import QtCore, QtWidgets as W
from desktopapp import i18n, jobs, reloadguide, completion
from desktopapp.ko import STRINGS
from desktopapp.paths import write_json
from desktopapp.window import Window


@pytest.fixture
def ui(tmp_path, monkeypatch):
    monkeypatch.setenv('A7C2_DESKTOP_DATA', str(tmp_path))
    # Exercise the actual new-install default, overriding the legacy Chinese fixture.
    from desktopapp.paths import load_settings
    monkeypatch.setattr('desktopapp.window.load_settings', load_settings)
    app = W.QApplication.instance() or W.QApplication([])
    windows = []
    def create(language=None):
        if language is not None:
            write_json(tmp_path / 'desktop.json', {'language': language})
        window = Window()
        window.timer.stop()
        windows.append(window)
        return window
    yield create, app, tmp_path
    for window in windows:
        window.process = None
        window.close()
    i18n.configure('zh_CN')


def test_new_install_defaults_to_korean_and_all_pages_open(ui):
    create, app, _ = ui
    window = create()
    assert window.language.currentData() == 'ko'
    assert window.nav.item(0).text() == '홈 · 한 번에 설치'
    assert window.setup_button.text() == '한 번에 설치'
    for index in range(7):
        window.nav.setCurrentRow(index)
        app.processEvents()
        assert window.pages.currentIndex() == index
        for label in window.pages.widget(index).findChildren(W.QLabel):
            assert not re.search('[\u4e00-\u9fff]', label.text()), label.text()
    assert window.common() == {'firmware': '2.01'}
    row = window.look_editor.add_row(4)
    assert row.slot.currentText() == '슬롯 4'
    assert window.current_job is None


def test_language_change_keeps_input_and_applies_on_next_launch(ui):
    create, _, root = ui
    window = create()
    window.fields['sound_source'].setText('/example/사용자 文件.wav')
    window.look_editor.add_row(4)
    with patch.object(W.QMessageBox, 'information'), patch.object(jobs, 'new_job') as job:
        window.language.setCurrentIndex(1)
    job.assert_not_called()
    settings = json.loads((root / 'desktop.json').read_text())
    assert settings['language'] == 'zh_CN'
    assert settings['sound_source'] == '/example/사용자 文件.wav'
    assert window.look_editor.values() == [{'slot': 4, 'action': 'restore'}]
    assert window.setup_button.text() == '한 번에 설치'
    reopened = create()
    assert reopened.nav.item(0).text() == '首页 · 一键安装'
    assert reopened.fields['sound_source'].text() == '/example/사용자 文件.wav'
    with patch.object(W.QMessageBox, 'information'):
        reopened.language.setCurrentIndex(0)
    korean = create()
    assert korean.setup_button.text() == '한 번에 설치'


@pytest.mark.parametrize('language', ['ko', 'zh_CN'])
def test_language_does_not_change_worker_action_or_slot_data(ui, language):
    create, _, _ = ui
    window = create(language)
    row = window.look_editor.add_row(4)
    row.action.setCurrentIndex(1)
    row.set_file('/example/원본 文件.a7look')
    row.name.setText('내 룩 原名')
    # File validation is covered by existing editor tests. Verify raw UI values here.
    assert window.look_batch_args()['operations'] == [dict(
        slot=4, action='write', path='/example/원본 文件.a7look', name='내 룩 原名')]
    window.look_editor.set_operations([dict(slot=4, action='restore')])
    with patch.object(W.QMessageBox, 'question', return_value=W.QMessageBox.Yes), \
            patch('desktopapp.window.QtCore.QProcess'):
        window.look_button.click()
    request = json.loads((window.current_job / 'request.private.json').read_text())
    assert request['action'] == 'direct_looks_import'
    assert request['arguments']['operations'] == [dict(slot=4, action='restore')]
    assert request['arguments']['firmware'] == '2.01'
    assert request['arguments']['power_confirmed'] is True
    assert not window.language.isEnabled()
    assert not window.stop.isEnabled()


def test_korean_confirmation_can_cancel_without_creating_job(ui):
    create, _, _ = ui
    window = create()
    window.look_editor.add_row(3)
    with patch.object(W.QMessageBox, 'question', return_value=W.QMessageBox.Cancel) as confirm, \
            patch.object(jobs, 'new_job') as new:
        window.look_button.click()
    new.assert_not_called()
    assert confirm.call_args.args[1] == '카메라 기록 시작'
    assert 'ILCE-7CM2' in confirm.call_args.args[2]
    assert '50%' in confirm.call_args.args[2]
    assert '사용자 슬롯 3' in confirm.call_args.args[2]


def test_guides_and_completion_switch_without_translating_user_names(ui):
    create, _, _ = ui
    create('ko')
    assert '최소 1분' in reloadguide.text()
    assert '프로그램 미기록' in reloadguide.text(mode='resource_reload')
    notice = reloadguide.sound_notice('sound_audition', dict(
        phase='temporary_pcm_registered_cold_reload_required_after_test'))
    assert '카메라 전원을 유지' in notice['title']
    state = dict(phase='COMPLETE', options=dict(looks=[dict(slot=1, name='原名 유지')]))
    assert '原名 유지' in completion.text(state)
    assert '선택한 작업을 마쳤고' in completion.text(state)
    create('zh_CN')
    assert '至少等待 1 分钟' in reloadguide.text()
    assert '原名 유지' in completion.text(state)


def test_translation_preserves_format_specifiers_and_file_extensions():
    specifiers = re.compile(r'%(?:\([^)]+\))?[#0\- +]*\d*(?:\.\d+)?[diouxXeEfFgGcrsa%]')
    for source, korean in STRINGS.items():
        assert specifiers.findall(source) == specifiers.findall(korean), source
        for extension in re.findall(r'\*\.[A-Za-z0-9]+', source):
            assert extension in korean, source
    assert i18n.tr('unmapped diagnostic') == 'unmapped diagnostic'


def test_standard_qt_confirmation_buttons_are_korean(ui):
    create, _, _ = ui
    create('ko')
    assert QtCore.QCoreApplication.translate('QPlatformTheme', '&Yes') == '예'
    assert QtCore.QCoreApplication.translate('QPlatformTheme', 'Cancel') == '취소'
    box = W.QMessageBox()
    box.setStandardButtons(W.QMessageBox.Yes | W.QMessageBox.Cancel)
    assert box.button(W.QMessageBox.Yes).text().replace('&', '') == '예'
    assert box.button(W.QMessageBox.Cancel).text().replace('&', '') == '취소'


def test_display_literals_have_catalog_entries():
    root = Path(__file__).resolve().parents[2] / 'src/desktopapp'
    for name in ('window.py', 'lookeditor.py', 'reloadguide.py', 'completion.py'):
        tree = ast.parse((root / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'tr':
                if node.args and isinstance(node.args[0], ast.Constant):
                    assert node.args[0].value in STRINGS, (name, node.lineno)


def test_windows_driver_controls_and_guide_use_korean(ui):
    create, _, _ = ui
    with patch('desktopapp.window.sys.platform', 'win32'):
        window = create('ko')
    automatic = window.findChild(W.QPushButton, 'action_usb_prepare')
    zadig = window.findChild(W.QPushButton, 'zadig_guide')
    assert '두 단계 드라이버' in automatic.text()
    assert 'Zadig로 수동 설치' in zadig.text()
    with patch.object(W.QDialog, 'exec', return_value=0) as shown:
        zadig.click()
    assert shown.call_count == 1
    from desktopapp.zadigguide import TEXT
    assert '054C 0336' in i18n.tr(TEXT)
    assert '관리자 권한' in i18n.tr(TEXT)
