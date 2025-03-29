<template>
  <div class="main-content">
    <el-card>
      <template #header>
        <div class="title fxsb">
          <div>LLM Config</div>
          <div>
            <el-link type="primary" class="no-select plr-6" @click="toEdit('base')" v-show="baseShow">
              {{ t('edit') }}
            </el-link>
            <el-link type="primary" class="no-select plr-6" @click="toShow('base')" v-show="baseEdit">
              {{ t('cancel') }}
            </el-link>
          </div>
        </div>
      </template>

      <!-- No Data -->
      <div class="no-data" v-show="baseNoData">{{ t('noData') }}</div>

      <!-- Show Data -->
      <div class="card-row-wrap" v-show="baseShow">
        <div class="card-row-item">
          <el-text>model:</el-text>
          <el-text>{{ llmConfig.model }}</el-text>
        </div>

        <div class="card-row-item">
          <el-text>base_url:</el-text>
          <el-text tag="p">{{ llmConfig.base_url }}</el-text>
        </div>

        <div class="card-row-item">
          <el-text>api_key:</el-text>
          <el-text>{{ llmConfig.api_key }}</el-text>
        </div>

        <div class="card-row-item">
          <el-text>max_tokens:</el-text>
          <el-text>{{ llmConfig.max_tokens }}</el-text>
        </div>

        <div class="card-row-item">
          <el-text>temperature:</el-text>
          <el-text>{{ llmConfig.temperature }}</el-text>
        </div>
      </div>

      <!-- Edit Module -->
      <el-form ref="ruleFormRef" :model="llmConfigUpd" status-icon :rules="rules" v-show="baseEdit">
        <div class="card-row-wrap">
          <div class="card-row-item">
            <el-text>model:</el-text>
            <el-form-item prop="model">
              <el-input v-model="llmConfigUpd.model" />
            </el-form-item>
          </div>

          <div class="card-row-item">
            <el-text>base_url:</el-text>
            <el-form-item prop="base_url">
              <el-input v-model="llmConfigUpd.base_url" />
            </el-form-item>
          </div>

          <div class="card-row-item">
            <el-text>api_key:</el-text>
            <el-form-item prop="api_key">
              <el-input v-model="llmConfigUpd.api_key" />
            </el-form-item>
          </div>

          <div class="card-row-item">
            <el-text>max_tokens:</el-text>
            <el-form-item prop="max_tokens">
              <el-input v-model="llmConfigUpd.max_tokens" />
            </el-form-item>
          </div>

          <div class="card-row-item">
            <el-text>temperature:</el-text>
            <el-form-item prop="temperature">
              <el-input v-model="llmConfigUpd.temperature" />
            </el-form-item>
          </div>

          <div class="card-row-aline fxc" v-show="baseEdit">
            <el-button class="mlr-10" @click="toShow('base')">{{ t('cancel') }}</el-button>
            <el-button type="primary" class="mlr-10" @click="submitForm">{{ t('submit') }}</el-button>
          </div>
        </div>
      </el-form>
    </el-card>
  </div>

</template>

<script setup>
import { ref, reactive, inject, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useConfig } from '@/store/config'
import { useI18n } from 'vue-i18n'

const utils = inject('utils')
const files = inject('files')
const verify = inject('verify')
const router = useRouter()
const config = useConfig()
const { t } = useI18n()

// 视图模式
const viewModel = reactive({
  base: 'show',
})

function toShow(model) {
  console.log("toShow:" + model)
  viewModel[model] = 'show'
}

function toEdit(model) {
  console.log("toEdit:" + model)
  viewModel[model] = 'edit'
}

const baseShow = computed(() => {
  return viewModel.base == 'show'
})

const baseEdit = computed(() => {
  return viewModel.base == 'edit'
})

const readConfigSuccess = ref(true)

const baseNoData = computed(() => {
  return baseShow && !readConfigSuccess.value
})

const llmConfig = reactive({
  model: null,
  base_url: null,
  api_key: null,
  max_tokens: null,
  temperature: null,
})

const llmConfigUpd = reactive({
  model: null,
  base_url: null,
  api_key: null,
  max_tokens: null,
  temperature: null,
})

function clearCache() {
  config.$reset()
  utils.pop(t('clearCacheSuccess'))
}

onMounted(() => {
  // 读取配置文件config/config.toml
  loadLlmConfig()
})

function loadLlmConfig() {
  const filePath = "@/../../config/config.toml"
  files.readTomlNode(filePath, "llm").then((node) => {
    console.log("config/config.toml: ", node)
    if (utils.isBlank(node)) {
      readConfigSuccess.value = false
      utils.pop(t('readTomlFailed'))
      return
    }
    utils.copyProps(node, llmConfig)
    utils.copyProps(node, llmConfigUpd)
  })
}

function saveLlmConfig() {
  const filePath = "@/../../config/config.toml"
  files.readAll(filePath)
  files.saveTomlNode(filePath, "llm", llmConfigUpd).then((resp) => {
    console.log("config/config.toml: ", resp)
    loadLlmConfig()
    toShow('llm')
  })
}

const ruleFormRef = ref()

const rules = reactive({
  model: [{ validator: verify.validator('notBlank'), trigger: 'blur' }],
  base_url: [{ validator: verify.validator('notBlank'), trigger: 'blur' }],
  api_key: [{ validator: verify.validator('notBlank'), trigger: 'blur' }],
  max_tokens: [{ validator: verify.validator('notBlank'), trigger: 'blur' }],
  temperature: [{ validator: verify.validator('notBlank'), trigger: 'blur' }],
})

const submitForm = async () => {
  try {
    await ruleFormRef.value.validate();
    if (!utils.hasDfProps(llmConfig, llmConfigUpd)) {
      ElMessage.success('未发生更改!');
      toShow('base')
      return
    }
    ElMessage.success('验证通过，提交表单');
    saveLlmConfig()
    toShow('base')
  } catch (error) {
    ElMessage.error('参数验证失败');
  }
}

</script>

<style scoped></style>
