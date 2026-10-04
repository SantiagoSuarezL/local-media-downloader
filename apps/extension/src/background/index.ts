import { getBridge } from '../browser/index'

chrome.runtime.onInstalled.addListener(() => {
  void getBridge()
})
