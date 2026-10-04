"""对应 TradingAgents 的 Msg Clear：角色结束后清空执行历史，只交接最终业务结果。"""

from videoagents.state import VideoState, clean_handoff


class ClearToolsNode:
    def __call__(self, state: VideoState) -> VideoState:
        # CLI 没有 messages reducer，无需 RemoveMessage 或 Anthropic 的占位消息。
        # 此节点不修改数据库中的调用台账和审计文件，只清理跨节点传递的上下文。
        return clean_handoff(state)
