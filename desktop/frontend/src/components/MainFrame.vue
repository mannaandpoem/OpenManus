<template>
  <el-container class="layout-container">
    <el-aside width="collapse" class="layout-aside" :class="shrink ? 'shrink' : ''">
      <div :class="menuCollapse ? 'fixed-menu-collapse fxc' : 'fixed-menu-expand fxsb'">
        <div v-show="!menuCollapse" class="menu-logo">
          <el-link type="primary" @click="refresh" class="pl-14 pr-4">
            <img v-if="isDark" src="@/assets/img/logo-w-sm.png" class="fxc" height="26px" alt="logo" />
            <img v-if="!isDark" src="@/assets/img/logo-b-sm.png" class="fxc" height="26px" alt="logo" />
          </el-link>
        </div>
        <el-link class="plr-10 w-56" @click="menuToggle">
          <el-icon :size="20">
            <Fold v-show="!menuCollapse" />
            <Expand v-show="menuCollapse" />
          </el-icon>
        </el-link>
      </div>

      <el-scrollbar class="scrollbar-menu-wrapper" :class="shrink ? 'shrink' : ''">
        <AsideMenu />
      </el-scrollbar>
    </el-aside>
    <el-container>
      <el-header>
        <TopHeader />
      </el-header>
      <el-main>
        <el-scrollbar style="width: 100%;">
          <!-- Router View Container -->
          <!-- { Component } = currently matched route component -->
          <RouterView v-slot="{ Component }">
            <!-- Cached Route Transition: Only keeps alive components with keepAlive meta flag
             Transition animation requires single root element in component Key ensures proper re-rendering on route path changes -->
            <transition :name="transitionName">
              <KeepAlive>
                <Component :is="Component" v-if="keepAlive" :key="$route.path" />
              </KeepAlive>
            </transition>
            <!-- Non-cached Route Transition: Fresh instance for other components
             Separate transition to prevent animation conflicts -->
            <transition :name="transitionName">
              <Component :is="Component" v-if="!keepAlive" :key="$route.path" />
            </transition>
          </RouterView>
        </el-scrollbar>
      </el-main>
    </el-container>
    <div class="aside-menu-shade">

    </div>
  </el-container>
</template>

<script setup>
import TopHeader from '@/components/TopHeader.vue'
import AsideMenu from '@/components/AsideMenu.vue'
import { ref, reactive, computed, watch, onBeforeMount } from 'vue'
import { useRouter, RouterView } from 'vue-router'
import { Expand, Fold } from '@element-plus/icons-vue'
import { showShade, closeShade } from '@/assets/js/shade'
import { useConfig } from '@/store/config'
import { useEventListener } from '@vueuse/core'
import { storeToRefs } from 'pinia'
import { useDark } from '@vueuse/core'

const router = useRouter()
const config = useConfig()
const isDark = useDark()

const { shrink, collapse, resizeCollapse } = storeToRefs(config)

const menuCollapse = computed(() => collapse.value || resizeCollapse.value)

const currentRoute = reactive(router.currentRoute)

// Default transition effect, slide to the left
let transitionName = 'slide-left'

const keepAlive = computed(() => {
  return currentRoute.value.meta.keepAlive
})

/**
 * Set the menu animation duration to 0ms on page refresh to prevent the menu from expanding or collapsing
 * with an animation. This ensures that the menu state remains consistent after a page reload.
 */
const menuAnimationDuration = ref(0)

// Function to toggle the menu between expanded and collapsed states
function menuToggle() {
  menuAnimationDuration.value = '300ms'
  if (menuCollapse.value) {
    // console.log("Extend menu")
    if (shrink.value) {
      // Expend the shade if menu is collapsing
      showShade(() => {
        // Callback function to close the shade after the menu has collapsed
        config.setCollapse(true)
      })
    }
    config.setCollapse(false)
  } else {
    // If the menu is in an expanded state, close the shade
    closeShade()
    config.setCollapse(true)
  }
  resizeCollapse.value = collapse.value
  console.log("collapse:", collapse.value, ", menuCollapse:", menuCollapse.value)
}

// Adaptive layout
function onAdaptiveLayout() {
  // Get the current window width
  const clientWidth = document.body.clientWidth
  // Determine if the aside menu should be shrunk based on the window width
  if (clientWidth < 800) {
    config.setShrink(true)
    config.setResizeCollapse(true)
  } else {
    config.setShrink(false)
    config.setResizeCollapse(false)
  }
  closeShade()
}

watch(() => router.currentRoute.value, (newValue, oldValue) => {
  // Toggle the menu when the route changes
  onAdaptiveLayout()
})

onBeforeMount(() => {
  onAdaptiveLayout()
  useEventListener(window, 'resize', onAdaptiveLayout)
})

function refresh() {
  // Reload the page
  location.reload()
}

</script>

<style scoped>
.layout-container {
  height: 100vh;
}

header {
  width: 100%;
  height: 44px;
  padding: 0px;
  /* width: calc(100% -32px);
    margin-left: 16px;
    margin-right: 16px;
    border-radius: 6px; */
  background-color: var(--el-fg-color);
  display: flex;
  justify-content: center;
  align-items: center;
}

aside {
  z-index: 9999999;
}

aside.shrink {
  width: 44px;
}

.layout-aside {
  margin: 0;
  height: 100vh;
  overflow: hidden;
  transition: width .3s ease;
}

main {
  height: calc(100vh - 44px);
  width: 100%;
  padding: 0px;
  overflow: hidden;
  background-color: var(--el-bg-color);
}

.menu-logo {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Keyframes for the menu collapse animation */
@keyframes menuCollapse {
  0% {
    width: 200px;
  }

  100% {
    width: 44px;
  }
}

/* Keyframes for the menu expand animation */
@keyframes menuExpand {
  0% {
    width: 44px;
  }

  100% {
    width: 200px;
  }
}

.fixed-menu-collapse {
  position: fixed;
  z-index: 9999;
  height: 44px;
  width: 44px;
  /* Reference to the keyframes */
  animation-name: menuCollapse;
  /* Duration of the animation */
  animation-duration: v-bind('menuAnimationDuration');
  animation-timing-function: ease-in-out;
  background-color: var(--el-fg-color);
}

.fixed-menu-expand {
  position: fixed;
  height: 44px;
  width: 200px;
  /* Reference to the keyframes */
  animation-name: menuExpand;
  /* Duration of the animation */
  animation-duration: v-bind('menuAnimationDuration');
  animation-timing-function: ease-in-out;
  background-color: var(--el-fg-color);
  /* border-bottom: 1px solid var(--el-bg-color); */
  z-index: 9999999;
}

.scrollbar-menu-wrapper {
  top: 45px;
  height: calc(100vh - 45px);
  background-color: var(--el-fg-color);
}

.scrollbar-menu-wrapper.shrink {
  position: fixed;
  left: 0;
  z-index: 9999999;
}
</style>
