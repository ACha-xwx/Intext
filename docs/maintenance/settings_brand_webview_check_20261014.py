"""Actual WebView2/desktop bridge acceptance; disposable settings and no API key."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from promptsmith.preferences import defaults, load_settings, save_preferences
from playwright.sync_api import sync_playwright, expect
import psutil


def application_windows(process):
    pids = {process.pid}
    pids.update(p.pid for p in psutil.Process(process.pid).children(recursive=True))
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    windows = []

    @callback_type
    def visit(handle, _):
        identity = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(handle, ctypes.byref(identity))
        title = ctypes.create_unicode_buffer(128)
        ctypes.windll.user32.GetWindowTextW(handle, title, len(title))
        if identity.value in pids and title.value in {'Intext', 'Unhandled exception in script'}:
            messages = []

            @callback_type
            def child(child_handle, _):
                text = ctypes.create_unicode_buffer(4096)
                ctypes.windll.user32.GetWindowTextW(child_handle, text, len(text))
                if text.value:
                    messages.append(text.value)
                return True

            ctypes.windll.user32.EnumChildWindows(handle, child, 0)
            windows.append((handle, title.value, messages))
        return True

    ctypes.windll.user32.EnumWindows(visit, 0)
    return windows


def close_window(process):
    for handle, _, _ in application_windows(process):
        ctypes.windll.user32.PostMessageW(handle, 0x10, 0, 0)  # Normal WM_CLOSE.


def run(executable, output):
    output.mkdir(parents=True, exist_ok=True)
    report = dict(kind='actual_frozen_webview2' if executable else 'actual_source_webview2', checks=[])

    def check(name, passed):
        report['checks'].append(dict(name=name, passed=bool(passed)))
        assert passed, name

    with tempfile.TemporaryDirectory(prefix='intext-brand-acceptance-') as isolated:
        settings = Path(isolated) / 'PromptSmith/settings.json'
        save_preferences(settings, dict(defaults(), model_directory_autorefresh=False),
            dict(provider='验收服务', model_provider='OpenAI', protocol='OpenAI Responses',
                 base_url='http://127.0.0.1:1/v1', model='gpt-6.1-sol'), api_key='')
        for launch in range(2):
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            environment = {key: value for key, value in os.environ.items()
                           if not key.startswith('PROMPTSMITH_')}
            environment.update(LOCALAPPDATA=isolated, PROMPTSMITH_SMOKE_CLOSE_MS='90000',
                WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=f'--remote-debugging-port={port}')
            command = [str(executable)] if executable else [sys.executable, str(ROOT/'run_promptsmith.py')]
            process = subprocess.Popen([*command, '--renderer', 'web'], cwd=isolated, env=environment,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline = time.monotonic() + 50
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f'Application exited before WebView2: {process.returncode}')
                    for _, title, messages in application_windows(process):
                        if title == 'Unhandled exception in script':
                            raise RuntimeError('Frozen startup failed: ' + '\n'.join(messages))
                    try:
                        with urlopen(f'http://127.0.0.1:{port}/json/version', timeout=.5):
                            break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError('WebView2 CDP did not become ready')
                        time.sleep(.15)
                with sync_playwright() as runtime:
                    browser = runtime.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
                    page = next(p for context in browser.contexts for p in context.pages if 'index.html' in p.url)
                    page.set_default_timeout(8000)
                    check('actual WebView2 page title', page.title() == 'Intext')
                    check('local PNG and SVG decoded', page.locator('.startup-title img').evaluate_all(
                        'images=>images.length===2&&images.every(e=>e.complete&&e.naturalWidth>0)'))
                    if launch == 0:
                        start = page.get_by_role('button', name='开始使用 Intext', exact=True)
                        expect(start).to_be_visible()
                        check('new logo and original full SVG', page.locator('.startup-title').evaluate(
                            "e=>e.querySelector('.startup-wordmark').src.endsWith('intext-logo.png')&&e.querySelector('.startup-name').src.endsWith('intext-wordmark.svg')"))
                        check('hero centered and fits', page.locator('.startup-group').evaluate(
                            'e=>{const r=e.getBoundingClientRect();return r.y>=0&&r.bottom<=innerHeight&&Math.abs(r.x+r.width/2-innerWidth/2)<1}'))
                        page.screenshot(path=str(output/'hero-light.png'))
                        start.click()
                        page.get_by_role('button', name='跳过教程', exact=True).click()
                    else:
                        expect(page.locator('#startup-hero')).to_be_hidden()
                        check('saved settings restored after restart', page.locator('html').get_attribute('data-theme') == 'dark')
                    page.wait_for_function('promptsmithStartup.entered')
                    check('sidebar keeps original English SVG', page.locator('.sidebar-wordmark').evaluate(
                        "e=>e.complete&&e.naturalWidth>0&&e.src.endsWith('intext-english.svg')"))
                    page.get_by_role('button', name='设置', exact=True).click()
                    expect(page.locator('#settings-page')).to_be_visible()
                    if launch == 0:
                        page.get_by_role('button', name='重命名', exact=True).click()
                        rename = page.get_by_role('dialog', name='重命名自定义供应商')
                        expect(rename).to_be_visible()
                        check('rename input uses shared settings appearance', page.locator('#settings-rename-name').evaluate(
                            "e=>{const a=getComputedStyle(e),b=getComputedStyle(document.querySelector('#settings-field-connection-base_url'));return e.classList.contains('settings-text-input')&&['borderRadius','padding','backgroundColor','fontSize'].every(k=>a[k]===b[k])}"))
                        rename.get_by_role('button', name='取消', exact=True).click()
                        removed = ['已有密钥由 Windows 加密保护', '各供应商独立保存接口',
                                   '模型配置可直接使用。测试连接只检查接口。', '修改自动保存，有效配置即可使用']
                        check('requested static hints removed', all(text not in page.locator('#settings-page').inner_text() for text in removed))
                    page.get_by_role('tab', name='界面', exact=True).click()
                    if launch == 0:
                        page.locator('#settings-field-conversation_width').fill('900')
                        page.locator('#settings-field-notification_seconds').fill('2')
                        page.locator('#settings-field-composer_theme').click()
                        page.locator('.settings-suggestions:popover-open').get_by_role('option', name='深色', exact=True).click()
                    page.wait_for_function("document.querySelector('#settings-field-notification_seconds').valueAsNumber===2")
                    page.wait_for_function("document.documentElement.dataset.theme==='dark'&&state.display_preferences.notification_seconds===2")
                    check('live settings saved to isolated disk', load_settings(settings).preferences['notification_seconds'] == 2)
                    page.screenshot(path=str(output/f'settings-dark-{launch}.png'))
                    page.get_by_role('button', name='返回工作区', exact=True).click()
                    expect(page.locator('#settings-page')).to_be_hidden()
                    check('live conversation width bounded', page.locator('#composer').bounding_box()['width'] <= 901)
                    check('new PNG remains full color in dark theme', page.locator('header .brand img').evaluate('e=>getComputedStyle(e).filter') == 'none')
                    check('no automatic runtime log files', not list((Path(isolated)/'PromptSmith/logs').glob('*.log')))
                    page.screenshot(path=str(output/f'workspace-dark-{launch}.png'))
                    report['user_agent'] = page.evaluate('navigator.userAgent')
                    browser.close()
                close_window(process)
                check('normal WebView2 shutdown', process.wait(timeout=15) == 0)
            except Exception as error:
                report['error'] = repr(error)
                try:
                    page.screenshot(path=str(output/'failure.png'))
                except Exception:
                    pass
                raise
            finally:
                if process.poll() is None:
                    close_window(process)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        for child in psutil.Process(process.pid).children(recursive=True):
                            child.kill()
                        process.kill()
                        process.wait(timeout=5)
                (output/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(checks=len(report['checks']), passed=all(row['passed'] for row in report['checks']),
                         kind=report['kind']), ensure_ascii=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.exe.resolve() if args.exe else None, args.output.resolve())
