from typing import Dict, List, Union

from app.agent.base import BaseAgent
from app.flow.base import BaseFlow, FlowType
from app.flow.planning import PlanningFlow


class FlowFactory:
    """Factory for creating different types of flows with support for multiple agents"""

    @staticmethod
    def create_flow(
        flow_type: FlowType,
        agents: Union[BaseAgent, List[BaseAgent], Dict[str, BaseAgent]],
        **kwargs,
    ) -> BaseFlow:
        """Create a flow of the specified type with the provided agents."""
        # 根据flow_type参数创建相应的flow
        if flow_type == FlowType.PLANNING:
            from app.flow.planning import PlanningFlow
            return PlanningFlow(agents, **kwargs)
        # ...other flow types...
        else:
            raise ValueError(f"Unknown flow type: {flow_type}")
