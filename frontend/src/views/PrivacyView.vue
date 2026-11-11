<script setup lang="ts">
// 公开页面：未登录可访问，主题跟随用户设置，不复用登录页的固定深色。
</script>

<template>
  <main class="privacy-page">
    <article class="privacy-doc">
      <header class="doc-head">
        <p class="eyebrow">隐私政策</p>
        <h1>我们怎么使用你的数据</h1>
        <p class="lede">下面每一条都对应系统当前的实际做法；功能调整时，本页会一起更新。</p>
      </header>

      <section>
        <h2>一、我们收集哪些数据</h2>
        <ul>
          <li>账号信息：注册邮箱与称呼；密码只以哈希形式保存，系统不保留明文密码。</li>
          <li>训练记录：你在语音、视频面试里说过的内容，每轮评分、报告、收藏与话术脚本。</li>
          <li>录音与录像：开启录制时，音视频文件保存在服务器，用于生成报告和回放。</li>
          <li>简历文本：使用「简历提问」上传 .docx 简历时，系统会把它提取成纯文本。</li>
        </ul>
      </section>

      <section>
        <h2>二、简历文本会发送给第三方大模型</h2>
        <p>
          使用简历提问时，提取出的简历文本会发给我们接入的第三方大模型服务，用来生成面试问题。
          当前接入 DeepSeek，接口本身兼容豆包、通义等兼容 API 的部署方式。发送前系统会先隐藏邮箱和手机号，
          替换为「[邮箱已隐藏]」「[手机号已隐藏]」；简历里的其他内容（项目、公司、经历等）会随请求一起发出。
          除生成问题外，这些文本不用于其他用途。
        </p>
      </section>

      <section>
        <h2>三、录音录像的存放与保留</h2>
        <ul>
          <li>存放位置：服务器上的 <code>static/recordings</code> 目录。</li>
          <li>保留时长：默认 30 天。</li>
          <li>清理方式：线上环境每 6 小时执行一次清理任务，删除超过保留期的文件。</li>
        </ul>
      </section>

      <section>
        <h2>四、镜头指标不用于身份识别</h2>
        <p>
          视频面试会用 MediaPipe 逐帧计算人脸几何指标：出镜率、眼神稳定率、头部稳定度、表情活跃度，以及构图与光线。
          这些指标只用来提示镜头表现，系统不做人脸身份识别，不与任何身份库比对，也不评价外貌或性格。
        </p>
      </section>

      <section>
        <h2>五、你的数据，你可以带走或删掉</h2>
        <ul>
          <li>导出：登录后在「个人资料」页点「导出我的数据」，可下载包含账号信息、训练记录、评分与话术的 JSON 文件。</li>
          <li>注销：在「个人资料」页输入密码并输入「注销」确认后，账号会被删除，同时级联删除你的训练会话、评分、消息记录与录像文件，操作不可恢复。</li>
        </ul>
      </section>

      <section>
        <h2>六、联系我们</h2>
        <p>
          隐私相关的问题可以发邮件到 <a href="mailto:privacy@example.com">privacy@example.com</a>
          （占位地址，上线前需替换为真实联系方式）。
        </p>
      </section>

      <footer class="doc-foot">
        <RouterLink class="back-link" to="/login">返回登录页</RouterLink>
      </footer>
    </article>
  </main>
</template>

<style scoped>
.privacy-page {
  min-height: 100vh;
  background: var(--bg);
  padding: 72px 24px 112px;
}

.privacy-doc {
  width: min(660px, 100%);
  margin: 0 auto;
  color: var(--text-2);
  font-size: 15px;
  line-height: 1.95;
}

.doc-head { margin-bottom: 44px; }
.eyebrow {
  margin: 0 0 10px;
  color: var(--accent-strong);
  font-size: 11px;
  letter-spacing: .16em;
}
h1 {
  margin: 0;
  color: var(--text);
  font-family: var(--font-display);
  font-size: 30px;
  font-weight: 600;
  letter-spacing: -.01em;
  line-height: 1.35;
}
.lede { margin: 14px 0 0; color: var(--text-3); font-size: 14px; line-height: 1.9; }

section { margin-bottom: 40px; }
h2 {
  margin: 0 0 12px;
  color: var(--text);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: .01em;
}
p { margin: 0; }
ul { margin: 0; padding-left: 20px; }
li { margin-bottom: 8px; }
li:last-child { margin-bottom: 0; }

code {
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--overlay-2);
  color: var(--text-2);
  font-size: 13.5px;
}

a { color: var(--accent-strong); text-decoration: none; border-bottom: 1px solid var(--accent-soft); }
a:hover { border-bottom-color: var(--accent-strong); }

.doc-foot { margin-top: 8px; padding-top: 28px; border-top: 1px solid var(--divider); }
.back-link { font-size: 14px; border: 0; }

@media (max-width: 620px) {
  .privacy-page { padding: 48px 20px 88px; }
  h1 { font-size: 25px; }
  .privacy-doc { font-size: 14.5px; }
}
</style>
