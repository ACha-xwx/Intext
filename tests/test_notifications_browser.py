"""User feedback on the production DOM; desktop bridge is disposable."""
from tests.test_frontend_review_regressions import browser, page, load
import pytest


def test_each_notification_expires_after_its_own_five_seconds_without_snapshot_replay(page):
    load(page)
    page.clock.install()
    page.clock.pause_at(page.evaluate("Date.now()"))
    page.evaluate("promptsmithNotifications.sync('first','第一条提醒')")
    page.clock.run_for(2000)
    page.evaluate("promptsmithNotifications.show('第二条提醒',{key:'second'})")
    page.clock.run_for(2999)
    assert page.locator('.notification-card:not(.closing)').count() == 2
    page.clock.run_for(1)
    assert page.locator('.notification-card:not(.closing)').count() == 1
    assert page.locator('.notification-card:not(.closing) .notification-body').inner_text() == '第二条提醒'
    page.clock.run_for(151)
    page.evaluate("promptsmithNotifications.sync('first','第一条提醒')")
    assert page.locator('.notification-card').count() == 1
    page.clock.run_for(1849)
    assert page.locator('.notification-card:not(.closing)').count() == 0
    page.clock.run_for(151)
    assert page.locator('.notification-card').count() == 0


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_countdown_bar_shrinks_evenly_from_right_to_left_without_changing_card_layout(page, theme):
    load(page, theme=theme)
    page.evaluate("promptsmithNotifications.show('五秒后关闭🧪',{variant:'warning'})")
    bar = page.locator('.notification-countdown')
    assert bar.count() == 1
    # Inspect the rendered animation at known elapsed times; no JS frame loop.
    samples = page.evaluate("""()=>{
      const bar=document.querySelector('.notification-countdown');
      const animation=bar.getAnimations()[0];animation.pause();
      const card=bar.closest('.notification-card');const samples=[];
      for(const elapsed of [0,1250,2500,3750,5000]){
        animation.currentTime=elapsed;
        const r=bar.getBoundingClientRect(),c=card.getBoundingClientRect();
        samples.push({left:r.left,width:r.width,cardWidth:c.width,cardHeight:c.height,bottom:r.bottom,cardBottom:c.bottom});
      }
      return {samples,timing:animation.effect.getTiming(),hidden:bar.getAttribute('aria-hidden')};
    }""")
    assert samples['timing']['duration'] == 5000
    assert samples['timing']['easing'] == 'linear'
    assert samples['hidden'] == 'true'
    full = samples['samples'][0]
    for item, fraction in zip(samples['samples'], [1, .75, .5, .25, 0]):
        assert abs(item['width'] - full['width'] * fraction) < 1
        assert abs(item['left'] - full['left']) < 1
        assert item['cardWidth'] == full['cardWidth']
        assert item['cardHeight'] == full['cardHeight']
        assert abs(item['bottom'] - item['cardBottom']) <= 2


def test_replacement_restarts_countdown_and_manual_close_cannot_expire_new_notice(page):
    load(page)
    page.clock.install()
    page.clock.pause_at(page.evaluate('Date.now()'))
    page.evaluate("promptsmithNotifications.show('旧提醒',{key:'replacement'})")
    page.clock.run_for(3000)
    page.evaluate("promptsmithNotifications.show('替换后的提醒',{key:'replacement'})")
    page.clock.run_for(2000)
    assert page.locator('.notification-body').inner_text() == '替换后的提醒'
    page.clock.run_for(2999)
    assert page.locator('.notification-card:not(.closing)').count() == 1
    page.clock.run_for(1)
    assert page.locator('.notification-card:not(.closing)').count() == 0
    page.clock.run_for(151)
    page.evaluate("promptsmithNotifications.show('手动关闭的提醒',{key:'manual'})")
    page.clock.run_for(2000)
    # Use the public close handler without advancing the paused clock via click.
    page.evaluate("document.querySelector('.notification-close').click()")
    page.clock.run_for(151)
    page.evaluate("promptsmithNotifications.show('再次提醒',{key:'manual'})")
    page.clock.run_for(3000)
    assert page.locator('.notification-body').inner_text() == '再次提醒'
    page.clock.run_for(2151)
    assert page.locator('.notification-card').count() == 0
    events = page.evaluate("calls.filter(c=>c.action==='diagnostic'&&c.args[1]==='notification dismissed').map(c=>c.args[2])")
    assert events.count('key=replacement reason=expired') == 1
    assert events.count('key=manual reason=expired') == 1
    assert events.count('key=manual reason=manual') == 1


def test_auto_close_restores_modal_keyboard_focus_and_does_not_emit_frame_logs(page):
    load(page)
    page.clock.install()
    page.clock.pause_at(page.evaluate('Date.now()'))
    page.evaluate("""()=>{
      const dialog=document.createElement('dialog');dialog.id='expiry-modal';
      dialog.innerHTML='<button>继续编辑</button>';document.body.append(dialog);dialog.showModal();
      promptsmithNotifications.show('草稿保留',{key:'modal-expiry',variant:'error'});
      document.querySelector('.notification-close').focus();
    }""")
    page.clock.run_for(4999)
    assert page.evaluate("document.activeElement.classList.contains('notification-close')")
    page.clock.run_for(152)
    assert page.locator('.notification-card').count() == 0
    assert page.evaluate("Boolean(document.activeElement.closest('#expiry-modal'))")
    events = page.evaluate("calls.filter(c=>c.action==='diagnostic'&&c.args[1].startsWith('notification ')).map(c=>c.args[1])")
    assert events == ['notification shown', 'notification dismissed']


def test_reduced_motion_keeps_five_second_expiry_without_decorative_animation(page):
    page.emulate_media(reduced_motion='reduce')
    load(page)
    page.clock.install()
    page.clock.pause_at(page.evaluate('Date.now()'))
    page.evaluate("promptsmithNotifications.sync('reduced-expiry','等待关闭')")
    assert page.locator('.notification-countdown').evaluate('e=>getComputedStyle(e).animationName') == 'none'
    page.clock.run_for(4999)
    assert page.locator('.notification-card').count() == 1
    page.clock.run_for(1)
    assert page.locator('.notification-card').count() == 0
    page.evaluate("promptsmithNotifications.sync('reduced-expiry','等待关闭')")
    assert page.locator('.notification-card').count() == 0


def test_enter_and_exit_animation_never_show_a_horizontal_scrollbar(page):
    load(page)
    page.clock.install()
    page.clock.pause_at(page.evaluate('Date.now()'))
    page.evaluate("promptsmithNotifications.show('动画中的消息',{key:'scrollbar'})")
    for closing in (False, True):
        if closing:
            page.evaluate("promptsmithNotifications.remove('scrollbar')")
        frames = page.evaluate("""()=>{
          const card=document.querySelector('.notification-card'),region=document.querySelector('#notifications');
          const animation=card.getAnimations()[0];animation.pause();const result=[];
          for(const fraction of [.1,.5,.9]){
            animation.currentTime=animation.effect.getTiming().duration*fraction;
            const style=getComputedStyle(region);
            result.push({overflowX:style.overflowX,overflowY:style.overflowY,
              scrollWidth:region.scrollWidth,clientWidth:region.clientWidth});
          }
          return result;
        }""")
        for frame in frames:
            assert frame['scrollWidth'] <= frame['clientWidth'] or frame['overflowX'] in ('hidden', 'clip')
            assert frame['overflowY'] == 'auto'

def test_modal_open_close_and_removal_keep_the_original_countdown_progress(page):
    load(page)
    page.evaluate("promptsmithNotifications.show('迁移时继续倒计时',{key:'modal-move'})")
    page.wait_for_timeout(1200)
    bar = page.locator('.notification-countdown')
    fraction = lambda: bar.evaluate('e=>e.getBoundingClientRect().width/e.parentElement.clientWidth')
    previous = fraction()
    for action in (
        "const d=document.createElement('dialog');d.id='moving-modal';document.body.append(d);d.showModal()",
        "document.querySelector('#moving-modal').close()",
        "document.querySelector('#moving-modal').showModal()",
        "document.querySelector('#moving-modal').remove()",
    ):
        page.evaluate('()=>{' + action + '}')
        page.wait_for_timeout(100)
        current = fraction()
        assert current <= previous + .015
        previous = current
    # Total lifetime belongs to the first appearance, regardless of parent.
    page.wait_for_function("!document.querySelector('.notification-card')", timeout=4000)


def test_remaining_notification_slides_up_when_previous_one_finishes_closing(page):
    load(page)
    page.evaluate("promptsmithNotifications.show('第一张',{key:'first-slot'});promptsmithNotifications.show('第二张',{key:'second-slot'})")
    page.wait_for_timeout(250)
    first = page.locator('[data-key=first-slot]')
    second = page.locator('[data-key=second-slot]')
    target = first.bounding_box()['y']
    start = second.bounding_box()['y']
    first.get_by_role('button', name='关闭通知', exact=True).click()
    page.wait_for_function("!document.querySelector('[data-key=first-slot]')", polling=5)
    after_removal = second.bounding_box()['y']
    assert target + 2 < after_removal <= start + 1
    page.wait_for_timeout(70)
    midway = second.bounding_box()['y']
    assert target < midway < after_removal
    page.wait_for_timeout(260)
    assert abs(second.bounding_box()['y'] - target) < 1


def test_consecutive_closes_continue_from_current_visual_position_without_resetting_timer(page):
    load(page)
    page.evaluate("""()=>{for(const key of ['first-moving','second-moving','third-moving'])
      promptsmithNotifications.show(key,{key});}""")
    page.wait_for_timeout(250)
    target = page.locator('[data-key=first-moving]').bounding_box()['y']
    page.evaluate("promptsmithNotifications.remove('first-moving',false)")
    # Freeze the in-progress visual shift halfway, then close the next card.
    continuity = page.evaluate("""()=>{
      const card=document.querySelector('[data-key=third-moving]');
      const move=card.getAnimations().find(a=>a.effect.getTiming().duration===240);
      move.pause();move.currentTime=120;
      const before=card.getBoundingClientRect().top;
      const countdownBefore=card.querySelector('.notification-countdown').getAnimations()[0].currentTime;
      promptsmithNotifications.remove('second-moving',false);
      const after=card.getBoundingClientRect().top;
      const countdownAfter=card.querySelector('.notification-countdown').getAnimations()[0].currentTime;
      return {before,after,countdownBefore,countdownAfter};
    }""")
    assert abs(continuity['before'] - continuity['after']) < 1
    assert continuity['countdownAfter'] >= continuity['countdownBefore']
    page.wait_for_timeout(300)
    assert abs(page.locator('[data-key=third-moving]').bounding_box()['y'] - target) < 1


def test_reduced_motion_repositions_remaining_notifications_immediately(page):
    page.emulate_media(reduced_motion='reduce')
    load(page)
    page.evaluate("promptsmithNotifications.show('第一张',{key:'reduced-first'});promptsmithNotifications.show('第二张',{key:'reduced-second'})")
    target = page.locator('[data-key=reduced-first]').bounding_box()['y']
    page.get_by_role('button', name='关闭通知', exact=True).first.click()
    second = page.locator('[data-key=reduced-second]')
    assert abs(second.bounding_box()['y'] - target) < 1
    assert second.evaluate('e=>e.getAnimations().length') == 0


def test_upward_shift_does_not_create_a_temporary_vertical_scrollbar(page):
    load(page)
    page.evaluate("promptsmithNotifications.show('第一张',{key:'vertical-first'});promptsmithNotifications.show('第二张',{key:'vertical-second'})")
    page.wait_for_timeout(250)
    page.evaluate("promptsmithNotifications.remove('vertical-first',false)")
    measurements = page.evaluate("""()=>{
      const card=document.querySelector('[data-key=vertical-second]'),region=document.querySelector('#notifications');
      const shift=card.getAnimations().find(a=>a.effect.getTiming().duration===240);
      shift.pause();const result=[];
      for(const fraction of [0,.25,.5,.75,1]){
        shift.currentTime=240*fraction;
        result.push({scrollHeight:region.scrollHeight,clientHeight:region.clientHeight,
          scrollWidth:region.scrollWidth,clientWidth:region.clientWidth});
      }
      return result;
    }""")
    for item in measurements:
        assert item['scrollHeight'] <= item['clientHeight']
        assert item['scrollWidth'] <= item['clientWidth']


def test_stable_overlay_passes_blank_clicks_through_and_keeps_real_overflow_scrollable(page):
    load(page)
    page.evaluate("promptsmithNotifications.show('短通知',{key:'click-through'})")
    box = page.locator('#message').bounding_box()
    page.mouse.click(box['x'] + box['width'] - 20, box['y'] + 15)
    assert page.evaluate("document.activeElement.id === 'message'")
    page.evaluate("""()=>{promptsmithNotifications.remove('click-through',false);
      for(let i=0;i<14;i++)promptsmithNotifications.show('可滚动通知 '+i,{key:'overflow-'+i});}""")
    region = page.locator('#notifications')
    assert region.evaluate('e=>e.scrollHeight>e.clientHeight')
    page.locator('.notification-card').first.hover()
    page.mouse.wheel(0, 350)
    page.wait_for_function("document.querySelector('#notifications').scrollTop > 100")
    page.locator('[data-key=overflow-13]').scroll_into_view_if_needed()
    assert page.locator('[data-key=overflow-13]').is_visible()


def test_notifications_stack_at_top_right_and_dismiss_without_snapshot_replay(page):
    notices = [dict(id=1, level="error", text="请求失败：输入仍保留。"),
               dict(id=2, level="warn", text="目录未保存：可以重试。")]
    state = load(page, notifications=notices)
    cards = page.locator(".notification-card")
    assert cards.count() == 2
    box = cards.first.bounding_box()
    assert box["y"] < 90 and box["x"] > 1440 / 2
    assert cards.first.locator("svg").count() == 2
    cards.first.get_by_role("button", name="关闭通知", exact=True).click()
    page.wait_for_timeout(250)
    assert cards.count() == 1
    page.evaluate("s=>promptsmithView.applySnapshot(s)", state)
    assert cards.count() == 1
    assert "目录未保存" in cards.inner_text()
    assert page.locator("#toast").count() == 0


def test_settings_failure_is_a_closable_notification_and_keeps_retry_and_draft(page):
    load(page, page="settings")
    page.evaluate("pywebview.api.dispatch=async()=>({ok:false,error_kind:'persistence',error:'模拟磁盘写入失败'})")
    field = page.get_by_label("模型 ID", exact=True)
    field.fill("retained-model")
    page.wait_for_timeout(650)
    assert page.locator(".notification-error").filter(has_text="模拟磁盘写入失败").count() == 1
    assert field.input_value() == "retained-model"
    assert page.get_by_role("button", name="重试自动保存", exact=True).is_visible()
    assert page.locator(".settings-error").is_hidden()


def test_notification_remains_clickable_above_native_modal(page):
    load(page)
    page.evaluate("""()=>{const dialog=document.createElement('dialog');dialog.id='modal-fixture';
      dialog.innerHTML='<button>保留编辑</button>';document.body.append(dialog);dialog.showModal();
      promptsmithNotifications.show('编辑失败，草稿保留',{variant:'error'});} """)
    page.wait_for_timeout(240)
    page.get_by_role("button", name="关闭通知", exact=True).click()
    page.wait_for_timeout(250)
    assert page.locator(".notification-card").count() == 0
    assert page.locator("#modal-fixture").evaluate("e=>e.open")
    assert page.evaluate("Boolean(document.activeElement.closest('#modal-fixture'))")


def test_empty_required_editor_field_uses_notification_instead_of_browser_balloon(page):
    load(page, editor=dict(id="required-fixture",kind="requirement",title="修改需求",message="",
                          fields=[dict(key="text",label="需求内容",type="text",value="",required=True)]))
    page.locator(".editor-save").click()
    assert page.locator(".notification-warning").filter(has_text="需求内容不能为空").count() == 1
    assert page.get_by_role("dialog",name="修改需求").is_visible()
    assert not page.evaluate("calls.some(c=>c.action==='editor_save')")


def test_editor_rejection_and_followup_snapshot_show_one_error_and_keep_draft(page):
    state=load(page,editor=dict(id="rejected-editor",kind="requirement",title="修改需求",error="",
                              fields=[dict(key="text",label="需求内容",value="原需求",required=True)]))
    page.get_by_label("需求内容",exact=True).fill("未提交草稿")
    state["editor"]["error"]="模拟保存失败，草稿保留。"
    page.evaluate("s=>{pywebview.api.dispatch=async()=>({ok:false,error:s.editor.error});pywebview.api.snapshot=async()=>({version:2,state:s});}",state)
    page.locator(".editor-save").click()
    page.wait_for_function("!inFlight&&document.querySelector('.notification-error')")
    assert page.locator(".notification-error").count()==1
    assert page.get_by_label("需求内容",exact=True).input_value()=="未提交草稿"
    assert page.locator(".editor-save").is_enabled()


@pytest.mark.parametrize("theme,width", [("light",1440),("dark",480)])
def test_long_unicode_feedback_wraps_and_does_not_execute_html_or_move_layout(page,theme,width):
    page.set_viewport_size(dict(width=width,height=540))
    load(page,theme=theme)
    before=page.locator("#message").bounding_box()
    text="中文🧪é👨‍👩‍👧‍👦<img src=x onerror=alert(1)>"*100
    page.evaluate("t=>promptsmithNotifications.show(t,{variant:'warning'})",text)
    page.wait_for_timeout(250)
    card=page.locator(".notification-card")
    box=card.bounding_box()
    assert box["x"]>=0 and box["x"]+box["width"]<=width
    assert page.locator(".notification-body").inner_text()==text
    assert card.locator("img").count()==0
    assert page.locator("#message").bounding_box()==before


def test_modal_removal_keeps_other_notifications_accessible(page):
    load(page)
    page.evaluate("""()=>{const d=document.createElement('dialog');d.id='temporary-modal';
      document.body.append(d);d.showModal();promptsmithNotifications.show('保留消息');d.remove();}""")
    page.wait_for_timeout(240)
    page.get_by_role("button",name="关闭通知",exact=True).click()
    page.wait_for_timeout(180)
    assert page.locator(".notification-card").count()==0


def test_reduced_motion_dismisses_immediately_and_snapshot_sync_does_not_replay(page):
    page.emulate_media(reduced_motion="reduce")
    load(page)
    page.evaluate("promptsmithNotifications.sync('fixture','请重试',{variant:'error'})")
    assert page.locator(".notification-card").evaluate("e=>getComputedStyle(e).animationName")=="none"
    page.get_by_role("button",name="关闭通知",exact=True).click()
    page.evaluate("promptsmithNotifications.sync('fixture','请重试',{variant:'error'})")
    assert page.locator(".notification-card").count()==0


def test_history_modal_allows_keyboard_to_close_validation_notification(page):
    load(page,history=dict(active="history-fixture",error="",entries=[dict(id="history-fixture",title="隔离会话",group="今天",stage="需求",pinned=False)]))
    page.locator(".history-row").first.hover()
    page.locator(".history-more").first.click()
    page.get_by_role("menuitem",name="重命名",exact=True).click()
    page.get_by_role("textbox",name="会话名称",exact=True).fill("")
    page.get_by_role("button",name="保存",exact=True).click()
    reachable=False
    for _ in range(7):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement.getAttribute('aria-label')==='关闭通知'"):
            reachable=True
            page.keyboard.press("Enter")
            break
    assert reachable
    assert page.evaluate("Boolean(document.activeElement.closest('.history-dialog'))")
