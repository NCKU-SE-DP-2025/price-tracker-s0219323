<template>
  <nav class="navbar" ref="navbar">
    <div class="title">
      <RouterLink to="/overview" @click="closeMenu">價格追蹤小幫手</RouterLink>
    </div>
    <div class="hamburger" @click="toggle" :class="{ active: isActive }" tabindex="0">
      <span></span>
      <span></span>
      <span></span>
    </div>
    <ul class="options" :class="{ active: isActive }">
      <li><RouterLink to="/overview" @click="closeMenu">物價概覽</RouterLink></li>
      <li><RouterLink to="/trending" @click="closeMenu">物價趨勢</RouterLink></li>
      <li><RouterLink to="/news" @click="closeMenu">相關新聞</RouterLink></li>
      <li v-if="!isLoggedIn"><RouterLink to="/login" @click="closeMenu">登入</RouterLink></li>
      <li v-else @click="handleLogout">Hi, {{getUserName}}! 登出</li>
    </ul>
  </nav>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/stores/auth'

const userStore = useAuthStore()
const isLoggedIn = computed(() => userStore.isLoggedIn)
const getUserName = computed(() => userStore.getUserName)

function handleLogout() {
  userStore.logout()
  closeMenu()
}

const isActive = ref(false)
function toggle() {
  isActive.value = !isActive.value
}
function closeMenu() {
  isActive.value = false
}

const navbar = ref(null)

function handleClickOutside(event) {
  if (navbar.value && !navbar.value.contains(event.target)) {
    closeMenu()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.navbar {
  display: flex;
  justify-content: space-between;
  background-color: #f3f3f3;
  padding: 1.5em;
  height: 4.5em;
  width: 100%;
  align-items: center;
  box-shadow: 0 0 5px #000000;
  position: relative;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  user-select: none;
}

.navbar *:focus {
  outline: none;
}

.title > a {
  font-size: 1.6em;
  font-weight: bold;
  color: #2c3e50 !important;
  text-decoration: none;
}

.options {
  list-style: none;
  display: flex;
  justify-content: space-around;
  margin: 0;
  padding: 0;
}

.options li {
  margin: 0 0.5em;
  font-size: 1.2em;
}

.options a {
  display: block;
  width: 100%;
  height: 100%;
  text-decoration: none;
  color: #575B5D;
  padding: 0.5em 1em;
  border-radius: 4px;
  transition: background-color 0.3s, font-weight 0.2s;
  cursor: pointer;
}

.options a:hover {
  font-weight: bold;
  background-color: #e6e6e6;
}

.options a.router-link-active {
  font-weight: bold;
  background-color: #dcdcdc;
  color: #2c3e50;
}

.options a.router-link-exact-active {
  background-color: #c9c9c9;
  color: #000;
}

.hamburger {
  display: none;
  flex-direction: column;
  justify-content: space-between;
  width: 30px;
  height: 25px;
  cursor: pointer;
  transition: transform 0.3s ease;
}

.hamburger span {
  display: block;
  height: 3px;
  background-color: black;
  border-radius: 2px;
  transition: 0.3s ease, transform 0.2s ease, background-color 0.2s ease;
  cursor: pointer;
}

.hamburger:hover span:nth-child(1) {
  transform: translateY(-2px) scaleX(1.1);
  background-color: #2c3e50;
}

.hamburger:hover span:nth-child(2) {
  transform: scaleX(1.1);
  background-color: #2c3e50;
}

.hamburger:hover span:nth-child(3) {
  transform: translateY(2px) scaleX(1.1);
  background-color: #2c3e50;
}

.hamburger.active {
  transform: rotate(90deg);
}

@media (max-width: 768px) {
  .hamburger {
    display: flex;
  }
  .options {
    display: none;
    position: absolute;
    top: 4.5em;
    left: 0;
    right: 0;
    flex-direction: column;
    background-color: #f3f3f3;
    padding: 0;
    border-radius: 0;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
  }
  .options.active {
    display: flex;
  }
  .options li {
    text-align: center;
    border-bottom: 1px solid #ddd;
  }
  .options li:last-child {
    border-bottom: none;
  }
  .options a {
    padding: 1em 0;
  }
}
</style>
