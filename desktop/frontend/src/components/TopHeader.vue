<template>
  <!-- 导航栏 -->
  <div class="nav-bar">
    <div class="fxc">
      <!-- 左侧固定下拉 -->
      <el-dropdown trigger="click" @command="handleSwitchModel" class="fxc plr-16">
        <span class="el-dropdown-link">
          {{ selectedModel }}
          <el-icon class="el-icon--right">
            <arrow-down />
          </el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-for="mod in modelList" :key="mod" :command="mod">
              {{ mod }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <!-- 刷新 -->
      <el-link @click="refresh">
        <el-icon :size="20">
          <Refresh />
        </el-icon>
      </el-link>
    </div>

    <!-- 右侧 -->
    <div class="fxc">
      <div class="mlr-8">
        <el-switch v-model="isDark" :active-action-icon="Moon" :inactive-action-icon="Sunny" width="40"
          style="--el-switch-on-color: #4c4d4f; --el-switch-off-color: #f2f2f2;" />
      </div>

      <!-- 右侧固定下拉 -->
      <el-dropdown trigger="click" @command="handleSwitchLang" class="fxc plr-16">
        <span class="el-dropdown-link">
          {{ selectedLang.name }}
          <el-icon class="el-icon--right">
            <arrow-down />
          </el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-for="lang in langList" :key="lang" :command="lang">
              {{ lang.name }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive, inject } from 'vue'
import { ArrowDown, Refresh, Moon, Sunny } from '@element-plus/icons-vue'
import { useConfig } from '@/store/config'
/** 暗黑主题切换 */
import { useDark } from '@vueuse/core'

const utils = inject("utils")
const files = inject("files")
const config = useConfig()
const isDark = useDark()

const modelList = ref([])

const selectedModel = ref(config.selectedModel)

function handleSwitchModel(mod) {
  // console.log("handleSwitchModel:", model)
  selectedModel.value = mod
  config.setSelectedModel(mod)
}

const langList = ref(config.langList)

const selectedLang = ref(config.selectedLang != null ? config.selectedLang : langList.value[0])

function handleSwitchLang(lang) {
  selectedLang.value = lang
  config.setSelectedLang(lang)
  // i18n.locale = lang.code
  location.reload()
}

const llmConfig = reactive({
  model: null,
  base_url: null,
  api_key: null,
  max_tokens: null,
  temperature: null,
})

function loadLlmConfig() {
  const filePath = "@/../../config/config.toml"
  files.readTomlNode(filePath, "llm").then((node) => {
    console.log("config/config.toml: ", node)
    if (utils.isBlank(node)) {
      utils.pop(t('readTomlFailed'))
      return
    }
    utils.copyProps(node, llmConfig)
    let model = node.model
    if (utils.isBlank(model)) {
      model = "No Model"
    }
    if (model.startsWith("\"")) {
      model = model.substring(1)
    }
    if (model.endsWith("\"")) {
      model = model.substring(0, model.length - 1)
    }
    utils.clearArray(modelList.value)
    modelList.value.push(model)
    if (selectedModel.value == null) {
      config.setSelectedModel(modelList.value[0])
    }
  })
}

onMounted(() => {
  // 读取配置文件config/config.toml
  loadLlmConfig()
})

function refresh() {
  location.reload()
}

</script>

<style scoped>
.nav-bar {
  display: flex;
  height: 44px;
  width: 100%;
  justify-content: space-between;
}

.el-dropdown-link {
  text-align: center;
  cursor: pointer;
  min-width: 40px;
  color: var(--el-color-primary);
  display: flex;
  align-items: center;
  /* 禁止双击选中文字 */
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  user-select: none;
}

.nav-menu {
  height: 100%;
  text-align: left;
  vertical-align: middle;
  display: flex;
  justify-content: start;
  align-items: center;
}

.nav-menu .item {
  width: 50px;
}

.nav-menu .profile {
  width: 100px;
}

.nav-menu .profile img {
  width: 40px;
  height: 30px;
  padding: 0 5px;
}
</style>
