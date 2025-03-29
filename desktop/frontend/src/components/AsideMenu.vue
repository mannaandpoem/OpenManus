<template>
  <el-menu class="el-menu-custom" :default-active="activeMenu()" :collapse="menuCollapse" @open="handleOpen"
    @close="handleClose" :popper-offset="8">

    <el-menu-item index="M02" @click="routeTo('/task')">
      <el-icon>
        <List />
      </el-icon>
      <span>{{ getMenuNameByCode('M02') }}</span>
    </el-menu-item>

    <el-menu-item index="M03" @click="routeTo('/history')">
      <el-icon>
        <Clock />
      </el-icon>
      <span>{{ getMenuNameByCode('M03') }}</span>
    </el-menu-item>

    <el-sub-menu index="M99" v-if="hasMenuPerm('M99')">
      <template #title>
        <el-icon>
          <setting />
        </el-icon>
        <span>{{ getMenuNameByCode('M99') }}</span>
      </template>
      <el-menu-item v-if="listSubMenu('M99') != null" v-for="secMenu in listSubMenu('M99')" :index="secMenu.index"
        @click="routeTo(secMenu.href)">
        {{ getMenuNameByCode(secMenu.index) }}
      </el-menu-item>
    </el-sub-menu>
  </el-menu>
</template>

<script setup>
import { List, Clock, Setting } from '@element-plus/icons-vue'
import { ref, computed, inject, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useConfig } from '@/store/config'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

const utils = inject('utils')
const { t } = useI18n()
const router = useRouter()
const config = useConfig()

const { collapse, resizeCollapse } = storeToRefs(config)

const menuCollapse = computed(() => collapse.value || resizeCollapse.value)

const handleOpen = (key, keyPath) => {
  // console.log(key, keyPath)
}
const handleClose = (key, keyPath) => {
  // console.log(key, keyPath)
}

// Menu List
const menuList = [
  {
    index: "M02",
    menuName: "menu.task",
    href: "/task"
  },
  {
    index: "M03",
    menuName: "menu.history",
    href: "/history"
  },
  {
    index: "M99",
    menuName: "menu.config.settings",
    href: null,
    subMenuList: [
      {
        index: "M9901",
        menuName: "menu.config.general",
        href: "/config/general"
      },
      {
        index: "M9902",
        menuName: "menu.config.llm",
        href: "/config/llm"
      },
    ]
  },
]

onMounted(() => {
  // Check menu position after refresh
  // activeMenu()
})

function hasMenuPerm(menuCode) {
  return menuList.some(menuLv1 => menuLv1.index == menuCode)
}

function listSubMenu(menuCode) {
  const matchedMenu = menuList.find(menuLv1 => menuLv1.index == menuCode)
  if (matchedMenu != null) {
    return matchedMenu.subMenuList
  }
  return null
}

watch(() => router.currentRoute.value.path, (newValue, oldValue) => {
  // console.log('LeftMenu侦听到router.currentRoute.value.path发生更新', newValue, oldValue)
  // Check menu position after route change
  activeMenu()
})

// Check activated menu position
function activeMenu() {
  const currRoute = router.currentRoute
  const path = currRoute.value.path
  // console.log("currRoute path:", path)
  let index = getIndexByPath(path)
  // console.log("index:", index)
  if (utils.notNull(index)) {
    return index
  }
  // No match, try to find menu for parent path
  const lastIndex = path.lastIndexOf('/')
  if (lastIndex != -1) {
    const newPath = path.substring(0, lastIndex)
    // console.log("newPath from parent path:", newPath)
    index = getIndexByPath(newPath)
    // console.log("index from parent path:", index)
    if (utils.notNull(index)) {
      return index
    }
  }
  return "1"
}

// Query menu index by path
function getIndexByPath(path) {
  for (let fstMenu of menuList) {
    // console.log(fstMenu.index, fstMenu.href == path)
    if (fstMenu.href == path) {
      // console.log("完整1级菜单匹配上")
      return fstMenu.index
    }
    const secMenuList = fstMenu.subMenuList
    if (utils.notEmpty(secMenuList)) {
      for (let secMenu of secMenuList) {
        // console.log(secMenu.index, secMenu.href == path)
        if (secMenu.href == path) {
          return secMenu.index
        }
        const thdMenuList = secMenu.subMenuList
        if (utils.notEmpty(thdMenuList)) {
          for (let thdMenu of thdMenuList) {
            if (thdMenu.href == path) {
              return thdMenu.index
            }
          }
          // If no third-level menu path matches, use the 'to' from the route configuration to find a match
          for (let thdMenu of thdMenuList) {
            const nodeList = routeMap.get(path)
            if (utils.isEmpty(nodeList)) {
              continue
            }
            for (let node of nodeList) {
              if (node.to == thdMenu.href) {
                // console.log("A match was found for node.to:", node.to)
                return thdMenu.index
              }
            }
          }
        }
      }
      // Iterate through each secondary menu item in the secMenuList
      for (let secMenu of secMenuList) {
        // console.log(secMenu.index, secMenu.href == path)
        const nodeList = routeMap.get(path)
        if (utils.isEmpty(nodeList)) {
          continue
        }
        for (let node of nodeList) {
          if (node.to == secMenu.href) {
            // console.log("匹配上node.to:", node.to)
            return secMenu.index
          }
        }
      }
    }
    // None of the menu items match the path, try to find a match for the 'to' from the route configuration

  }
}

// get routes configuration
const routes = router.options.routes
// console.log("routes:", routes)
const routeMap = new Map()
routes.forEach(lv1 => {
  // console.log("lv1:", lv1)
  buildRoutePer(lv1)
})
// console.log(routeMap)

function buildRoutePer(lv1) {
  const lv2List = lv1.children
  if (utils.isEmpty(lv2List)) {
    const node1 = {
      title: lv1.meta.title
    }
    const nodeList = [node1]
    routeMap.set(lv1.path, nodeList)
    return
  }
  lv2List.forEach(lv2 => {
    // console.log("lv2:", lv2)
    const node1 = {
      title: lv1.meta.title
    }
    const node2 = {
      title: lv2.meta.title
    }
    const nodeList = [node1, node2]
    if (utils.notNull(lv2.meta.subTitle)) {
      const node3 = {
        title: lv2.meta.subTitle,
        to: null
      }
      nodeList.push(node3)
    }
    routeMap.set(lv1.path + '/' + lv2.path, nodeList)
  })
}

function routeTo(href) {
  if (href == undefined || href == null || href == '') {
    return
  }
  router.push(href)
}

function getMenuNameByCode(code) {
  for (let menu of menuList) {
    if (menu.index == code) {
      return t(menu.menuName)
    }
    if (menu.subMenuList != null) {
      for (let subMenu of menu.subMenuList) {
        if (subMenu.index == code) {
          return t(subMenu.menuName)
        }
      }
    }
  }
  return t(code)
}

</script>

<style scoped>
span {
  /* Prevent text selection from double-clicking */
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  user-select: none;
}

span {
  /* Font size */
  font-size: 16px;
}

li {
  /* Font size */
  font-size: 15px;
}

.el-menu-custom {
  border-right: none;
  --el-menu-item-height: 40px;
  --el-menu-sub-item-height: 36px;
  padding-top: 6px;
  padding-bottom: 6px;
  margin-left: 6px;
  margin-right: 6px;
}

/** When the menu is collapsed, redefine the hover menu height */
.el-menu-item {
  min-width: 32px;
  height: 36px;
  line-height: 36px;
}

.el-menu-custom .el-menu--collapse {
  width: 32px;
}

.el-menu-custom:not(.el-menu--collapse) {
  width: 188px;
}
</style>
