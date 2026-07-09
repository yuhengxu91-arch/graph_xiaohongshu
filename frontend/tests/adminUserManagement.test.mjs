import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const routerSource = readFileSync(new URL('../src/router.js', import.meta.url), 'utf8')
const sidebarSource = readFileSync(new URL('../src/components/layout/AppSidebar.vue', import.meta.url), 'utf8')
const mainAppSource = readFileSync(new URL('../src/MainApp.vue', import.meta.url), 'utf8')
const apiSource = readFileSync(new URL('../src/api.js', import.meta.url), 'utf8')

test('admin user management page is routed and hidden from non-admin sidebar', () => {
  assert.match(routerSource, /AdminUsersPage/)
  assert.match(routerSource, /name:\s*'admin_users'/)
  assert.match(sidebarSource, /canManageUsers/)
  assert.match(sidebarSource, /人员管理/)
  assert.match(mainAppSource, /:can-manage-users="canManageUsers"/)
})

test('frontend api exposes admin user list and role update endpoints', () => {
  assert.match(apiSource, /getAdminUsers/)
  assert.match(apiSource, /setAdminUserRole/)
  assert.match(apiSource, /\/admin\/users/)
  assert.match(apiSource, /\/admin\/users\/\$\{userId\}\/admin/)
})
