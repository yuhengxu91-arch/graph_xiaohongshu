import assert from 'node:assert/strict'
import test from 'node:test'

import {
  PROMPT_APPLY_STORAGE_KEY,
  clearPromptApplyPayload,
  consumePromptApplyPayload,
  savePromptApplyPayload,
} from '../src/utils/promptApply.js'

function createMemoryStorage() {
  const values = new Map()
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  }
}

test('prompt apply payload is consumed once for the matching category', () => {
  const storage = createMemoryStorage()
  savePromptApplyPayload(storage, {
    prompt_id: 'prompt-1',
    category: 'poster',
    content: '生成春日海报',
    created_at: 1000,
  })

  assert.deepEqual(consumePromptApplyPayload(storage, 'poster', 1000), {
    prompt_id: 'prompt-1',
    category: 'poster',
    content: '生成春日海报',
    created_at: 1000,
  })
  assert.equal(consumePromptApplyPayload(storage, 'poster', 1000), null)
})

test('prompt apply payload is discarded when the category does not match', () => {
  const storage = createMemoryStorage()
  savePromptApplyPayload(storage, {
    prompt_id: 'prompt-2',
    category: 'workflow',
    content: 'AI 教育趋势',
    created_at: 1000,
  })

  assert.equal(consumePromptApplyPayload(storage, 'poster', 1000), null)
  assert.equal(storage.getItem(PROMPT_APPLY_STORAGE_KEY), null)
})

test('prompt apply payload rejects unknown categories and blank content', () => {
  const storage = createMemoryStorage()

  assert.throws(() => savePromptApplyPayload(storage, {
    prompt_id: 'prompt-3',
    category: 'other',
    content: '其他内容',
    created_at: 1000,
  }))
  assert.throws(() => savePromptApplyPayload(storage, {
    prompt_id: 'prompt-4',
    category: 'poster',
    content: '   ',
    created_at: 1000,
  }))
})

test('prompt apply payload discards malformed and expired data', () => {
  const storage = createMemoryStorage()
  storage.setItem(PROMPT_APPLY_STORAGE_KEY, '{invalid')
  assert.equal(consumePromptApplyPayload(storage, 'poster', 1000), null)

  savePromptApplyPayload(storage, {
    prompt_id: 'prompt-5',
    category: 'poster',
    content: '过期海报',
    created_at: 1000,
  })
  assert.equal(consumePromptApplyPayload(storage, 'poster', 301001), null)
})

test('storage write failures are exposed to the caller', () => {
  const storage = {
    setItem() {
      throw new Error('storage disabled')
    },
  }

  assert.throws(() => savePromptApplyPayload(storage, {
    prompt_id: 'prompt-6',
    category: 'poster',
    content: '无法保存',
    created_at: 1000,
  }), /storage disabled/)
})

test('prompt apply payload can be cleared after a failed navigation', () => {
  const storage = createMemoryStorage()
  savePromptApplyPayload(storage, {
    prompt_id: 'prompt-7',
    category: 'poster',
    content: '待清理',
    created_at: 1000,
  })

  clearPromptApplyPayload(storage)

  assert.equal(storage.getItem(PROMPT_APPLY_STORAGE_KEY), null)
})
