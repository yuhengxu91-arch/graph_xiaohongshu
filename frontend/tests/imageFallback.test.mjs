import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

import {
  countDegradedItems,
  fallbackNotice,
  FALLBACK_NOTICE,
} from '../src/utils/imageFallback.js'
import {
  batchTaskHeaders,
  createBatchTaskContext,
} from '../src/utils/batchTaskAccess.js'

test('fallback notice is emitted only for degraded results', () => {
  assert.equal(fallbackNotice({ degraded: false }), '')
  assert.equal(fallbackNotice({ degraded: true }), FALLBACK_NOTICE)
  assert.equal(fallbackNotice({ degraded_count: 2 }), FALLBACK_NOTICE)
  assert.equal(
    countDegradedItems([
      { degraded: true },
      { degraded: false },
      { degraded: true },
    ]),
    2,
  )
})

test('anonymous task context keeps token in memory request headers', () => {
  const context = createBatchTaskContext({
    task_id: 'task-1',
    access_token: 'secret-token',
  })
  assert.deepEqual(context, {
    taskId: 'task-1',
    accessToken: 'secret-token',
  })
  assert.deepEqual(batchTaskHeaders(context), {
    'X-Task-Access-Token': 'secret-token',
  })
  assert.deepEqual(batchTaskHeaders({ taskId: 'owned-task' }), {})
})

test('admin and result components wire fallback controls and notices', () => {
  const preference = readFileSync(
    new URL('../src/components/profile/PreferenceForm.vue', import.meta.url),
    'utf8',
  )
  const result = readFileSync(
    new URL('../src/components/poster/ResultDisplay.vue', import.meta.url),
    'utf8',
  )
  const template = readFileSync(
    new URL('../src/components/poster/PanelTemplate.vue', import.meta.url),
    'utf8',
  )
  const api = readFileSync(
    new URL('../src/api.js', import.meta.url),
    'utf8',
  )
  assert.match(preference, /参与自动降级/)
  assert.match(preference, /fallback_priority/)
  assert.match(preference, /capabilities\.aspect_ratios/)
  assert.match(result, /fallbackNotice/)
  assert.match(result, /batchStatus\.degraded_count/)
  assert.match(template, /batchStatus\.degraded_count/)
  assert.match(api, /export function streamBatchStatus/)
  assert.match(api, /batchTaskHeaders/)
})
