<template>
  <div class="main-content fc">
    <el-scrollbar ref="scrollRef" style="width: 100%;">
      <div class="output-area" v-show="taskInfo.taskId != null">

        <div class="dialog-user">
          <div class="blank"></div>
          <div class="content">
            <el-text class="title">
              {{ t('user') }}
            </el-text>
            <el-text class="prompt">
              {{ taskInfo.prompt }}
            </el-text>
          </div>
        </div>

        <div class="dialog-ai">
          <el-text class="title"> OpenManus-AI </el-text>

          <div class="card-row-wrap">
            <div class="card-row-aline">
              <el-timeline class="wp-100">
                <el-timeline-item v-for="(step, index) in taskInfo.stepList" :key="index" :timestamp="step.createdDt"
                  placement="top">
                  <el-card>
                    <div>
                      <h4 class="color-label mr-10" :class="utils.colorByLabel('step')">
                        STEP
                      </h4>
                      <el-text>{{ step.result }}</el-text>
                    </div>
                    <el-divider />
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
                  </el-card>
                </el-timeline-item>
              </el-timeline>
            </div>
          </div>
        </div>
        <div>
          <el-text class="pr-10">任务状态:</el-text>
          <el-text>{{ taskInfo.status }}</el-text>
        </div>

      </div>
    </el-scrollbar>

    <div class="input-area">
      <div class="input-box">
        <el-icon @click="uploadFile" class="add-file-area" :size="24">
          <FolderAdd />
        </el-icon>
        <el-input ref="promptEle" type="textarea" v-model="prompt" class="input-style" style="border: none;"
          :autosize="{ minRows: 1, maxRows: 4 }" autofocus placeholder="请输入指令" @keydown.enter="handleInputEnter" />

        <el-link class="send-area">
          <el-icon @click="sendPrompt" :size="24" v-show="!loading">
            <Promotion />
          </el-icon>
          <el-icon @click="stop" :size="24" v-show="loading">
            <CircleClose />
          </el-icon>
        </el-link>
      </div>

      <div>
        <el-text class="tips">以上内容由OpenManus生成, 仅供参考和借鉴</el-text>
      </div>
    </div>
  </div>

</template>

<script setup>
import { ref, reactive, inject, computed, onMounted, onUnmounted } from 'vue'
import { FolderAdd, Promotion, Eleme, CircleClose } from '@element-plus/icons-vue'
import { useConfig } from '@/store/config'
import { useI18n } from 'vue-i18n'
import i18n from '@/locales/i18n'

const utils = inject('utils')
const config = useConfig()
const { t } = useI18n()

const prompt = ref('')
const promptEle = ref(null)

const eventTypes = ['think', 'tool', 'act', 'log', 'run', 'message']
const eventSource = ref(null)

const taskInfo = computed(() => {
  return config.getCurrTask()
})

const loading = ref(false)
const scrollRef = ref(null)

const backendUrl = computed(() => {
  return config.getBackendUrl()
})

// 建立EventSource连接
const buildEventSource = (taskId) => {
  loading.value = true
  eventSource.value = new EventSource('http://localhost:5172/tasks/' + taskId + '/events')
  eventSource.value.onmessage = (event) => {
    console.log('Received data:', event.data)
    // 在这里处理接收到的数据 不起作用
  }

  eventTypes.forEach(type => {
    eventSource.value.addEventListener(type, (event) => handleEvent(event, type))
  })

  eventSource.value.onerror = (error) => {
    console.error('EventSource failed:', error)
    // 处理错误情况
    loading.value = false
    eventSource.value.close()
    taskInfo.value.status = "failed"
    utils.pop("任务执行失败", "error")
  }

}

const handleEvent = (event, type) => {
  console.log('Received event, type:', type, event.data)
  //  clearInterval(heartbeatTimer);
  try {
    const data = JSON.parse(event.data);
    console.log("type:", type, "data:", data)
    if (eventSource.value.readyState === EventSource.CLOSED) {
      console.log('Connection is closed');
    }
    if (type == "complete" || data.status == "completed") {
      console.log('task completed');
      loading.value = false
      eventSource.value.close()
      taskInfo.value.status = "success"
      utils.pop("任务已完成", "success")
      return
    }
    // autoScroll(stepContainer);
    buildOutput(taskInfo.value.taskId)
  } catch (e) {
    console.error(`Error handling ${type} event:`, e);
  }
}

async function buildOutput(taskId) {
  // 同步执行,确保数据顺序
  await utils.awaitGet('http://localhost:5172/tasks/' + taskId).then(data => {
    console.log("task info resp:", data)
    buildStepList(data.steps)
    console.log("stepList:", taskInfo.value.stepList)
    // 滚动到底部
    setTimeout(() => {
      scrollToBottom()
    }, 100)
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
        return
      }
    } else {
      // 子步骤
      const subStep = {
        type: step.type,
        idx: idx,
        result: step.result,
        createdDt: utils.dateFormat(new Date())
      }
      // 判定添加到stepList中的哪个元素元素的subList中
      console.log("stepList:", taskInfo.value.stepList, "idx:", idx)
      let parentStep = null
      const pStepIndex = taskInfo.value.stepList.findIndex(parentStep => parentStep.idx > idx)
      console.log("pStepIndex:", pStepIndex)
      if (pStepIndex != -1) {
        // 取pStep的上一个元素
        parentStep = taskInfo.value.stepList[pStepIndex - 1]
      } else {
        // 不存在时, 添加到stepList最后一个元素末尾
        parentStep = taskInfo.value.stepList[taskInfo.value.stepList.length - 1]
      }
      console.log("parentStep:", parentStep)
      const existSubStep = parentStep.subList.find(existSubStep => existSubStep.idx == idx)
      if (!existSubStep) {
        // 不存在时, 添加到末尾
        parentStep.subList.push(subStep)
        return
      }
    }
  })

}

onUnmounted(() => {
  // 组件卸载时关闭EventSource连接
  if (eventSource.value) {
    eventSource.value.close()
  }
})

function handleInputEnter(event) {
  console.log("handleInputEnter:", event)
  event.preventDefault()
  sendPrompt()
}

function uploadFile() {
  utils.pop("暂不支持,开发中", "warning")
}

const scrollToBottom = () => {
  if (scrollRef.value) {
    console.log("scrollRef:", scrollRef.value, scrollRef.value.wrapRef)
    const container = scrollRef.value.wrapRef
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  }
}

// 发送提示词
function sendPrompt() {
  // 关闭之前的连接
  if (eventSource.value != null) {
    eventSource.value.close()
  }

  if (utils.isBlank(prompt.value)) {
    utils.pop("Please enter a valid prompt", "error")
    promptEle.value.focus()
    return
  }

  utils.post('http://localhost:5172/tasks', { prompt: prompt.value }).then(data => {
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
    // 发送完成后清空输入框
    prompt.value = ''
    // 建立新的EventSource连接
    buildEventSource(data.task_id)

    console.log("new task created:", newTask)
  }).catch(error => {
    console.error('Failed to create task:', error)
  })
}

function stop() {
  console.log("stop")
  loading.value = false
  eventSource.value.close()
  taskInfo.value.status = "terminated"
  utils.pop("用户终止任务", "error")
}

</script>

<style scoped>
.output-area {
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


.dialog {
  width: 100%;
}


.dialog-ai {
  margin-bottom: 16px;
  background-color: var(--el-fg-color);
  border-radius: 12px;
}

.dialog-ai .title {
  margin: 6px 12px;
  font-size: 15px;
}

.input-area {
  flex-grow: 0;
  width: 100%;
  max-height: 180px;
  padding-left: 80px;
  padding-right: 80px;
  padding-top: 12px;
  padding-bottom: 12px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.input-box {
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
  color: var(--el-text-color-secondary);
  font-size: 12px;
  padding-top: 10px;
}

.sub-step-time {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
