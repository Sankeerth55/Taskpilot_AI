"""
Monitoring and Analytics API Routes for TaskPilot AI

Provides endpoints for:
- System health
- Performance metrics
- Cache statistics
- Error tracking
- Quality analytics
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from app.core.logging_config import get_performance_monitor, get_agent_monitor
from app.core.cache import get_all_cache_stats, clear_all_caches
from app.core.error_recovery import get_error_recovery_manager
from app.core.quality_validation import get_output_validator


router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/health")
async def get_system_health():
    """
    Get overall system health status.
    
    Returns:
        - status: overall system status
        - uptime: system uptime (if tracked)
        - agents: agent health status
    """
    try:
        perf_monitor = get_performance_monitor()
        error_manager = get_error_recovery_manager()
        
        perf_stats = perf_monitor.get_summary()
        error_stats = error_manager.get_error_summary()
        
        # Determine overall health
        success_rate = perf_stats.get('success_rate', 0)
        recovery_rate = error_stats.get('recovery_rate', 0)
        
        if success_rate >= 95 and recovery_rate >= 80:
            status = "healthy"
        elif success_rate >= 80 and recovery_rate >= 60:
            status = "degraded"
        else:
            status = "unhealthy"
        
        return {
            "status": status,
            "timestamp": perf_stats.get('total_tasks', 0),
            "metrics": {
                "success_rate": success_rate,
                "recovery_rate": recovery_rate,
                "total_tasks": perf_stats.get('total_tasks', 0),
                "total_errors": error_stats.get('total_errors', 0)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/performance")
async def get_performance_metrics():
    """
    Get detailed performance metrics.
    
    Returns:
        - Task execution statistics
        - Average duration
        - Success/failure rates
    """
    try:
        perf_monitor = get_performance_monitor()
        stats = perf_monitor.get_summary()
        
        return {
            "performance": stats,
            "details": {
                "total_tasks": stats.get('total_tasks', 0),
                "successful": stats.get('successful', 0),
                "failed": stats.get('failed', 0),
                "success_rate": stats.get('success_rate', 0),
                "avg_duration": round(stats.get('avg_duration', 0), 2),
                "total_time": round(stats.get('total_time', 0), 2)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")


@router.get("/agents")
async def get_agent_statistics():
    """
    Get statistics for all agents.
    
    Returns:
        - Per-agent execution stats
        - Success rates
        - Average durations
    """
    try:
        agent_names = ["fetcher", "analyzer", "planner", "reporter"]
        agents_stats = {}
        
        for agent_name in agent_names:
            monitor = get_agent_monitor(agent_name)
            agents_stats[agent_name] = monitor.get_stats()
        
        return {
            "agents": agents_stats,
            "summary": {
                "total_agents": len(agent_names),
                "avg_success_rate": sum(
                    stats.get('success_rate', 0) 
                    for stats in agents_stats.values()
                ) / len(agent_names) if agent_names else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent statistics: {str(e)}")


@router.get("/cache")
async def get_cache_statistics():
    """
    Get cache performance statistics.
    
    Returns:
        - Hit rates
        - Cache sizes
        - Eviction counts
    """
    try:
        cache_stats = get_all_cache_stats()
        
        return {
            "cache_stats": cache_stats,
            "summary": {
                "total_caches": len(cache_stats.get('agent_caches', {})),
                "avg_hit_rate": sum(
                    cache.get('hit_rate', 0) 
                    for cache in cache_stats.get('agent_caches', {}).values()
                ) / max(len(cache_stats.get('agent_caches', {})), 1)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache statistics: {str(e)}")


@router.post("/cache/clear")
async def clear_caches():
    """
    Clear all caches.
    
    Use this to force fresh results or free memory.
    """
    try:
        clear_all_caches()
        return {
            "status": "success",
            "message": "All caches cleared successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear caches: {str(e)}")


@router.get("/errors")
async def get_error_statistics():
    """
    Get error tracking and recovery statistics.
    
    Returns:
        - Error counts by category
        - Error severity distribution
        - Recovery rates
    """
    try:
        error_manager = get_error_recovery_manager()
        error_summary = error_manager.get_error_summary()
        recent_errors = error_manager.get_recent_errors(limit=20)
        
        return {
            "summary": error_summary,
            "recent_errors": [
                {
                    "type": err.get('error_type'),
                    "category": err.get('category'),
                    "severity": err.get('severity'),
                    "recovered": err.get('recovered'),
                    "message": err.get('error_message', '')[:100]
                }
                for err in recent_errors
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get error statistics: {str(e)}")


@router.get("/quality")
async def get_quality_statistics():
    """
    Get output quality statistics.
    
    Returns:
        - Average quality scores
        - Quality distribution
        - Per-agent quality metrics
    """
    try:
        validator = get_output_validator()
        quality_stats = validator.get_validation_stats()
        
        return {
            "quality_stats": quality_stats,
            "summary": {
                "total_validations": quality_stats.get('total_validations', 0),
                "overall_avg": quality_stats.get('overall_average_score', 0),
                "quality_distribution": quality_stats.get('quality_distribution', {})
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get quality statistics: {str(e)}")


@router.get("/dashboard")
async def get_dashboard_data():
    """
    Get comprehensive dashboard data.
    
    Returns all monitoring data in one call for dashboard display.
    """
    try:
        perf_monitor = get_performance_monitor()
        error_manager = get_error_recovery_manager()
        validator = get_output_validator()
        
        agent_names = ["fetcher", "analyzer", "planner", "reporter"]
        agents_stats = {}
        for agent_name in agent_names:
            monitor = get_agent_monitor(agent_name)
            agents_stats[agent_name] = monitor.get_stats()
        
        return {
            "performance": perf_monitor.get_summary(),
            "agents": agents_stats,
            "cache": get_all_cache_stats(),
            "errors": error_manager.get_error_summary(),
            "quality": validator.get_validation_stats(),
            "timestamp": perf_monitor.get_summary().get('total_tasks', 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")
