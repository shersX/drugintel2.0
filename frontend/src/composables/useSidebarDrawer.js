import { ref } from 'vue'

const drawerOpen = ref(false)

export function useSidebarDrawer() {
  function openDrawer() {
    drawerOpen.value = true
  }
  function closeDrawer() {
    drawerOpen.value = false
  }
  function toggleDrawer() {
    drawerOpen.value = !drawerOpen.value
  }
  return {
    drawerOpen,
    openDrawer,
    closeDrawer,
    toggleDrawer,
  }
}
