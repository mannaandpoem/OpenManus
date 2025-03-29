<template>
  <div class="main-content fc">
    <el-scrollbar ref="scrollRef" class="scrollWrap">
      <div class="dialog-area" v-show="taskInfo.taskId != null">

        <div class="dialog-user">
          <div class="blank"></div>
          <div class="content">
            <div class="title fxc">
              <img src="@/assets/img/user.png" class="user-img" />
              <el-text>
                {{ t('user') }}
              </el-text>
            </div>
            <el-text class="prompt">
              {{ taskInfo.prompt }}
            </el-text>
          </div>
        </div>

        <div class="dialog-ai">
          <div class="fxsb">
            <el-text class="title"> OpenManus-AI </el-text>
            <div class="plr-10">
              <el-link type="primary" class="no-select plr-6" @click="expandAll" v-show="notAllExpanded">
                {{ t('expandAll') }}
              </el-link>
              <el-link type="primary" class="no-select plr-6" @click="collapseAll" v-show="notAllCollapsed">
                {{ t('collapseAll') }}
              </el-link>
            </div>
          </div>
          <div class="card-row-wrap">
            <div class="card-row-aline">
              <el-collapse v-model="activeNames" @change="handleChange" class="wp-100">
                <el-collapse-item v-for="(step, index) in taskInfo.stepList" :key="index" :name="step.stepNo"
                  :icon="ArrowRight">
                  <template #title>
                    <div class="fxsb wp-100">
                      <div>
                        <el-text class="collapse-color-label mr-10" :class="utils.colorByLabel('step')">
                          {{ t('step') }}
                        </el-text>
                        <el-text class="pl-10">{{ step.result }}</el-text>
                      </div>
                      <el-text class="tips-text plr-10">{{ step.createdDt }}</el-text>
                    </div>
                  </template>
                  <div v-for="(subStep, subIndex) in step.subList">
                    <div class="fxsb mtb-10">
                      <el-text> {{ subStep.type }} </el-text>
                      <el-text class="sub-step-time"> {{ subStep.createdDt }} </el-text>
                    </div>
                    <div>
                      <el-text> {{ subStep.result }} </el-text>
                    </div>
                    <el-divider v-if="subIndex != step.subList.length - 1" />
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>

          </div>
        </div>
      </div>
    </el-scrollbar>

    <div class="ctrl-area">
      <div class="task-area wp-100" v-show="!newTaskFlag">
        <div class="generated fxc">
          <div class="generated-label">{{ t('generatedContent') }}</div>
          <div class="generated-folder">You Can Check Generated Files Here, This Function Is In Developing.</div>
        </div>
      </div>

      <div class="input-area">
        <div class="progress-area w-80">
          <!-- progress-wrap是flex-column布局,器元素高度不会撑开父元素高度 -->
          <div class="progress-wrap">
            <el-progress type="dashboard" class="mt-10" :percentage="taskInfo.percentage"
              :status="taskInfo.progressStatus" :stroke-width="6" :width="60" v-show="taskInfo.status != null">
              <template #default="{ percentage }">
                <span class="percentage-value">{{ percentage }}%</span>
              </template>
            </el-progress>
            <el-text class="progress-text">{{ taskInfo.status }}</el-text>
          </div>
        </div>

        <div class="input-box">
          <el-icon @click="uploadFile" class="add-file-area" :size="24">
            <FolderAdd />
          </el-icon>
          <el-input ref="promptEle" type="textarea" v-model="prompt" class="input-style" style="border: none;"
            :autosize="{ minRows: 1, maxRows: 4 }" autofocus :placeholder="t('promptInputPlaceHolder')"
            @keydown.enter="handleInputEnter" />

          <el-link class="send-area">
            <el-icon @click="sendPrompt" :size="24" v-show="!loading && taskInfo.status != 'running'">
              <Promotion />
            </el-icon>
            <el-icon @click="stop" :size="24" v-show="loading || taskInfo.status == 'running'">
              <CircleClose />
            </el-icon>
          </el-link>
        </div>
      </div>

      <div class="tips">
        <el-text class="tips-text">{{ t('openManusAgiTips') }}</el-text>
      </div>
    </div>
  </div>

</template>

<script setup>
import { ref, reactive, watch, inject, computed, onMounted, onUnmounted } from 'vue'
import { FolderAdd, Promotion, CircleClose, ArrowRight } from '@element-plus/icons-vue'
import { useConfig } from '@/store/config'
import { useI18n } from 'vue-i18n'

const utils = inject('utils')
const files = inject('files')
const config = useConfig()
const { t } = useI18n()

const prompt = ref('')
const promptEle = ref(null)

const eventTypes = ['think', 'tool', 'act', 'log', 'run', 'message']
const eventSource = ref(null)

const newTaskFlag = ref(false)

const taskInfo = computed(() => {
  if (newTaskFlag.value) {
    return {}
  }
  return config.getCurrTask()
})

const serverConfig = ({
  host: null,
  port: null,
})

const loading = ref(false)
const scrollRef = ref(null)

const activeNames = ref([])

const notAllExpanded = computed(() => {
  return taskInfo.value.stepList != null && activeNames.value.length != taskInfo.value.stepList.length
})

const notAllCollapsed = computed(() => {
  return activeNames.value.length != 0
})

const handleChange = (val) => {
  console.log("handleChange:", val)
}
// Expand task log when first loading and auto collapse after 10s.
function autoExpandCollapse(stepNo) {
  scrollToBottom()
  if (activeNames.value.includes(stepNo)) {
    return
  }
  // console.log("autoExpandCollapse:", stepNo)
  const hasSubStepList = taskInfo.value.stepList.some(step => {
    // console.log("stepNo:", step.stepNo, "subList:", JSON.stringify(step.subList))
    return step.stepNo == stepNo && step.subList != null && step.subList.length > 0
  })
  console.log("stepNo", stepNo, "hasSubStepList:", hasSubStepList)
  if (!hasSubStepList) {
    return
  }
  activeNames.value.push(stepNo)
  setTimeout(() => {
    scrollToBottom()
  }, 500)
}

// Expand/Collapse all
function expandAll() {
  taskInfo.value.stepList.filter(item => {
    if (activeNames.value.includes(item.stepNo)) {
      return
    }
    activeNames.value.push(item.stepNo)
    setTimeout(() => {
      scrollToBottom()
    }, 500)
  })
}

watch(activeNames.value, (newVal, oldVal) => {
  console.log("activeNames changed:", newVal, oldVal)
})


function collapseAll() {
  utils.clearArray(activeNames.value)
}

// 建立EventSource连接
const buildEventSource = (taskId) => {
  loading.value = true
  eventSource.value = new EventSource(remoteBaseUrl.value + '/tasks/' + taskId + '/events')
  eventSource.value.onmessage = (event) => {
    console.log('Received data:', event.data)
    // 在这里处理接收到的数据 不起作用 可能是服务端接口有问题
  }

  eventTypes.forEach(type => {
    eventSource.value.addEventListener(type, (event) => handleEvent(event, type))
  })

  /* eventSource.value.onerror = (error) => {
     console.error('EventSource failed:', error)
     // 处理错误情况 可能是服务端接口有问题
     // loading.value = false
     // eventSource.value.close()
     // taskInfo.value.status = "failed"
     // taskInfo.value.progressStatus = "exception"
     // utils.pop(t('taskExecFailed'), "error")
   } */

}

const handleEvent = (event, type) => {
  // console.log('Received event, type:', type, event.data)
  //  clearInterval(heartbeatTimer)
  try {
    const data = JSON.parse(event.data)
    // console.log("type:", type, "data:", data)
    if (eventSource.value.readyState === EventSource.CLOSED) {
      // console.log('Connection is closed')
    }
    if (type == "complete" || data.status == "completed") {
      // console.log('task completed')
      loading.value = false
      taskInfo.value.status = "success"
      taskInfo.value.progressStatus = "success"
      utils.pop("任务已完成", "success")
      return
    }
    // autoScroll(stepContainer)
    buildOutput(taskInfo.value.taskId)
  } catch (e) {
    console.error(`Error handling ${type} event:`, e)
  }
}

async function buildOutput(taskId) {
  // 同步执行,确保数据顺序
  await utils.awaitGet(remoteBaseUrl.value + '/tasks/' + taskId).then(data => {
    // console.log("task info resp:", data)
    buildStepList(data.steps)
    // console.log("stepList:", taskInfo.value.stepList)
  })
}

// 封装stepList
const buildStepList = (steps) => {
  // stepList
  steps.forEach((step, idx) => {
    // 步骤
    if (step.type == "log" && step.result.startsWith("Executing step")) {
      const stepStr = step.result.replace("Executing step ", "").replace("\n", "")
      const stepNo = stepStr.split("/")[0]
      const stepCount = stepStr.split("/")[1]
      if (taskInfo.value.stepList.length < stepNo) {
        // 添加此step到stepList
        const parentStep = {
          type: "log",
          idx: idx,
          stepNo: stepNo,
          result: stepStr,
          subList: [],
          createdDt: utils.dateFormat(new Date())
        }
        taskInfo.value.stepList.push(parentStep)
        taskInfo.value.percentage = Math.floor((stepNo / stepCount) * 100)
        return
      }
      scrollToBottom()
    } else {
      // 子步骤
      const subStep = {
        type: step.type,
        idx: idx,
        result: step.result,
        createdDt: utils.dateFormat(new Date())
      }
      // 判定添加到stepList中的哪个元素元素的subList中
      // console.log("stepList:", taskInfo.value.stepList, "idx:", idx)
      let parentStep = null
      const pStepIndex = taskInfo.value.stepList.findIndex(parentStep => parentStep.idx > idx)
      // console.log("pStepIndex:", pStepIndex)
      if (pStepIndex != -1) {
        // 取pStep的上一个元素
        parentStep = taskInfo.value.stepList[pStepIndex - 1]
      } else {
        // 不存在时, 添加到stepList最后一个元素末尾
        parentStep = taskInfo.value.stepList[taskInfo.value.stepList.length - 1]
      }
      // console.log("parentStep:", parentStep)
      const existSubStep = parentStep.subList.find(existSubStep => existSubStep.idx == idx)
      if (!existSubStep) {
        // 不存在时, 添加到末尾
        parentStep.subList.push(subStep)
      }
      autoExpandCollapse(taskInfo.value.stepList[taskInfo.value.stepList.length - 1].stepNo)
    }
    scrollToBottom()
  })
  scrollToBottom()
}

onMounted(() => {
  // 读取配置文件config/config.toml
  loadServerConfig()
  if (taskInfo.value.status == "running") {
    taskInfo.value.status = null
  }
  startNewTask()
})

function loadServerConfig() {
  const filePath = "@/../../config/config.toml"
  files.readTomlNode(filePath, "server").then((node) => {
    console.log("config/config.toml: ", node)
    if (utils.isBlank(node)) {
      utils.pop(t('readTomlFailed'))
      return
    }
    utils.copyProps(node, serverConfig)
  })
}

onUnmounted(() => {
  // 组件卸载时关闭EventSource连接
  if (eventSource.value) {
    eventSource.value.close()
  }
})

function handleInputEnter(event) {
  // console.log("handleInputEnter:", event)
  event.preventDefault()
  sendPrompt()
}

function uploadFile() {
  utils.pop(t('inDevelopment'), "warning")
}

const scrollToBottom = () => {
  if (scrollRef.value) {
    // console.log("scrollRef:", scrollRef.value, scrollRef.value.wrapRef)
    const container = scrollRef.value.wrapRef
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  }
}

// 发送提示词
function sendPrompt() {
  if (utils.isBlank(prompt.value)) {
    utils.pop("Please enter a valid prompt", "error")
    promptEle.value.focus()
    return
  }

  if (taskInfo.value.status == "running") {
    utils.pop("请先终止当前任务", "error")
    return
  }

  // 关闭之前的连接
  if (eventSource.value != null) {
    eventSource.value.close()
  }

  utils.post(remoteBaseUrl.value + '/tasks', { prompt: prompt.value }).then(data => {
    if (!data.task_id) {
      throw new Error('Invalid task ID')
    }
    const newTask = {
      taskId: data.task_id,
      prompt: prompt.value,
      status: "running",
      createdDt: utils.dateFormat(new Date()),
      stepList: []
    }
    // 保存历史记录
    config.addTaskHistory(newTask)
    newTaskFlag.value = false
    // 发送完成后清空输入框
    prompt.value = ''
    // 建立新的EventSource连接
    buildEventSource(data.task_id)

    // console.log("new task created:", newTask)
  }).catch(error => {
    console.error('Failed to create task:', error)
  })
}

function stop() {
  // console.log("stop")
  loading.value = false
  // console.log("eventSource:", eventSource.value, "taskInfo:", taskInfo.value)
  if (eventSource.value != null) {
    eventSource.value.close()
  }

  taskInfo.value.status = "terminated"
  taskInfo.value.progressStatus = "exception"
  utils.pop("用户终止任务", "error")
}

function startNewTask() {
  // console.log("startNewTask:", taskInfo.value)
  if (taskInfo.value.status == "running") {
    utils.pop("请先终止当前任务", "error")
    return
  }
  newTaskFlag.value = true
  prompt.value = ''
  utils.clearArray(activeNames.value)
}


const remoteBaseUrl = computed(() => {
  let url
  if (utils.notBlank(serverConfig.host)) {
    url = serverConfig.host
    if (url.startsWith("\"")) {
      url = url.substring(1)
    }
    if (url.endsWith("\"")) {
      url = url.substring(0, url.length - 1)
    }
    if (utils.notBlank(serverConfig.port)) {
      url = url + ":" + serverConfig.port
    }
    if (!url.startsWith("http")) {
      url = "http://" + url
    }
  } else {
    // default
    url = "http://localhost:5172"
  }
  return url
})

</script>

<style scoped>
.dialog-area {
  flex-grow: 1;
}

.dialog-user {
  display: flex;
  justify-content: center;
  align-items: space-between;
  margin-bottom: 16px;
}

.dialog-user .blank {
  flex-grow: 1;
}

.dialog-user .content {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: end;
  border-radius: 12px;
  background-color: var(--el-fg-color);
}

.dialog-user .title {
  /** 防止子元素宽度被设置为100%, 子元素的align-self设置除auto和stretch之外的值 */
  align-self: flex-end;
  margin: 6px 16px;
  font-size: 15px;
}

.dialog-user .prompt {
  /** 防止子元素宽度被设置为100%, 子元素的align-self设置除auto和stretch之外的值 */
  align-self: flex-end;
  margin: 0px 16px 6px 16px;
}

.dialog-user .user-img {
  width: 20px;
  height: 20px;
  margin-right: 2px;
  margin-bottom: 4px;
}

.dialog {
  width: 100%;
}

.dialog-ai {
  background-color: var(--el-fg-color);
  border-radius: 12px;
}

.dialog-ai .title {
  margin: 6px 12px;
  font-size: 15px;
}

.ctrl-area {
  flex-grow: 0;
  width: 100%;
  max-height: 200px;
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.ctrl-area .task-area {
  width: 100%;
  padding-left: 10px;
  padding-right: 7px;
  margin-bottom: 12px;
  background-color: var(--el-fg-color);
  border-radius: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.percentage-value {
  display: block;
  font-size: 16px;
}

.generated {
  flex-grow: 1;
  width: 100%;
  height: 68px;
  padding-left: 16px;
}

.generated-label {
  width: 80px;
  text-align: right;
}

.generated-folder {
  width: 100%;
  min-height: 54px;
  margin-left: 16px;
  background-color: var(--el-bg-color);
  border-radius: 6px;
}

.input-area {
  width: 100%;
  padding-right: 80px;
  border-radius: 16px;
  display: flex;
  justify-content: center;
  align-items: end;
}

.progress-area {
  align-self: center;
  flex-grow: 0;
  /* margin-left: -6px;
  margin-right: 10px; */
}

.progress-wrap {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  width: 80px;
  height: 54px;
  margin-left: -10px;
}

.progress-text {
  margin-top: -10px;
  width: 70px;
  text-align: center;
}


.input-box {
  flex-grow: 1;
  width: 100%;
  border-radius: 16px;
  background-color: var(--el-fg-color);
  display: flex;
  justify-content: center;
  align-items: center;
}

.input-style {
  width: 100%;
  padding-top: 12px;
  padding-bottom: 12px;
}

.input-style :deep(.el-textarea__inner) {
  outline: none;
  border: none;
  resize: none;
  box-shadow: none;
}

.add-file-area {
  margin-left: 16px;
  margin-right: 8px;
}

.send-area {
  margin-left: 8px;
  margin-right: 16px;
}

.tips {
  padding-top: 8px;
}

.tips-text {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.sub-step-time {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.icon-ele {
  margin: 0 8px 0 auto;
  color: #409eff;
}

.collapse-color-label {
  margin-top: 10px;
  margin-bottom: 10px;
  padding-left: 10px;
  padding-right: 10px;
  height: 24px;
  line-height: 24px;
  border-radius: 6px;
}
</style>
