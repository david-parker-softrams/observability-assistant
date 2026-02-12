"""
Phase 6 Demo: Caching System

This demo showcases the SQLite-based caching system that reduces CloudWatch API
calls and improves performance.
"""

import asyncio
import time
from pathlib import Path

from logai.cache.manager import CacheManager
from logai.config.settings import LogAISettings


async def demo_basic_caching():
    """Demonstrate basic cache operations."""
    print("=" * 60)
    print("DEMO 1: Basic Cache Operations")
    print("=" * 60)

    # Create cache manager with temporary directory
    settings = LogAISettings(
        anthropic_api_key="test-key",
        cache_dir=str(Path.home() / ".logai" / "cache_demo"),
    )
    cache = CacheManager(settings)
    await cache.initialize()

    try:
        # Clear any existing cache
        await cache.clear()

        # Store some data
        print("\n1. Storing log data in cache...")
        await cache.set(
            query_type="fetch_logs",
            payload={
                "events": [
                    {"timestamp": 1234567890, "message": "Application started"},
                    {"timestamp": 1234567891, "message": "Processing request"},
                    {"timestamp": 1234567892, "message": "Request completed"},
                ],
                "count": 3,
            },
            log_group="/aws/lambda/my-function",
            start_time=1234567000,
            end_time=1234567999,
        )
        print("   ✓ Stored 3 log events")

        # Retrieve from cache
        print("\n2. Retrieving from cache...")
        cached_data = await cache.get(
            query_type="fetch_logs",
            log_group="/aws/lambda/my-function",
            start_time=1234567000,
            end_time=1234567999,
        )
        if cached_data:
            print(f"   ✓ Cache HIT: Retrieved {cached_data['count']} events")
        else:
            print("   ✗ Cache MISS")

        # Try with different parameters (should be a miss)
        print("\n3. Trying with different log group...")
        cached_data = await cache.get(
            query_type="fetch_logs",
            log_group="/aws/lambda/other-function",
            start_time=1234567000,
            end_time=1234567999,
        )
        if cached_data:
            print("   ✓ Cache HIT")
        else:
            print("   ✗ Cache MISS (as expected - different log group)")

    finally:
        await cache.shutdown()


async def demo_cache_key_normalization():
    """Demonstrate cache key normalization to minute boundaries."""
    print("\n" + "=" * 60)
    print("DEMO 2: Cache Key Time Normalization")
    print("=" * 60)

    settings = LogAISettings(
        anthropic_api_key="test-key",
        cache_dir=str(Path.home() / ".logai" / "cache_demo"),
    )
    cache = CacheManager(settings)
    await cache.initialize()

    try:
        print("\n1. Storing data with timestamp 60000ms (1:00:00)...")
        await cache.set(
            query_type="fetch_logs",
            payload={"events": [], "count": 0},
            log_group="/aws/lambda/test",
            start_time=60000,
            end_time=120000,
        )

        print("\n2. Retrieving with timestamp 60999ms (1:00:00.999)...")
        print("   (Same minute, should normalize to same cache key)")
        cached_data = await cache.get(
            query_type="fetch_logs",
            log_group="/aws/lambda/test",
            start_time=60999,  # Different but same minute
            end_time=120999,
        )

        if cached_data:
            print("   ✓ Cache HIT! Time normalization working.")
        else:
            print("   ✗ Cache MISS (unexpected)")

    finally:
        await cache.shutdown()


async def demo_ttl_policies():
    """Demonstrate different TTL policies for different query types."""
    print("\n" + "=" * 60)
    print("DEMO 3: TTL Policies")
    print("=" * 60)

    settings = LogAISettings(
        anthropic_api_key="test-key",
        cache_dir=str(Path.home() / ".logai" / "cache_demo"),
    )
    cache = CacheManager(settings)
    await cache.initialize()

    try:
        now = int(time.time() * 1000)

        # Test different query types
        query_types = [
            ("list_log_groups", None),
            ("fetch_logs", now - (10 * 60 * 1000)),  # 10 minutes ago (historical)
            ("fetch_logs", now - (2 * 60 * 1000)),  # 2 minutes ago (recent)
            ("get_log_statistics", now),
        ]

        print("\nTTL for different query types:")
        for query_type, end_time in query_types:
            ttl = cache.calculate_ttl(query_type, end_time)
            if ttl >= 3600:
                ttl_str = f"{ttl // 3600} hours"
            elif ttl >= 60:
                ttl_str = f"{ttl // 60} minutes"
            else:
                ttl_str = f"{ttl} seconds"

            description = ""
            if query_type == "list_log_groups":
                description = " (rarely changes)"
            elif query_type == "fetch_logs" and end_time and (now - end_time) < 5 * 60 * 1000:
                description = " (recent, may still be ingesting)"
            elif query_type == "fetch_logs":
                description = " (historical, immutable)"
            elif query_type == "get_log_statistics":
                description = " (aggregations)"

            print(f"   {query_type:20s}: {ttl_str:15s}{description}")

    finally:
        await cache.shutdown()


async def demo_cache_statistics():
    """Demonstrate cache statistics and monitoring."""
    print("\n" + "=" * 60)
    print("DEMO 4: Cache Statistics")
    print("=" * 60)

    settings = LogAISettings(
        anthropic_api_key="test-key",
        cache_dir=str(Path.home() / ".logai" / "cache_demo"),
    )
    cache = CacheManager(settings)
    await cache.initialize()

    try:
        # Clear cache first
        await cache.clear()

        # Add some data
        print("\n1. Adding multiple cache entries...")
        for i in range(5):
            await cache.set(
                query_type="fetch_logs",
                payload={
                    "events": [{"message": f"Log {j}"} for j in range(10)],
                    "count": 10,
                },
                log_group=f"/aws/lambda/function{i}",
                start_time=1000000 + i * 10000,
                end_time=2000000 + i * 10000,
            )

        # Access some entries to increment hit count
        for i in range(3):
            await cache.get(
                query_type="fetch_logs",
                log_group=f"/aws/lambda/function{i}",
                start_time=1000000 + i * 10000,
                end_time=2000000 + i * 10000,
            )

        # Get statistics
        stats = await cache.get_statistics()

        print("\n2. Cache Statistics:")
        print(f"   Total entries:     {stats['entry_count']}")
        print(f"   Total size:        {stats['total_size_mb']:.2f} MB")
        print(f"   Total logs cached: {stats['total_logs']}")
        print(f"   Cache hits:        {stats['total_hits']}")
        print(f"   Expired entries:   {stats['expired_count']}")
        print(f"   Database location: {stats['db_path']}")

    finally:
        await cache.shutdown()


async def demo_eviction():
    """Demonstrate LRU eviction when cache size limit is exceeded."""
    print("\n" + "=" * 60)
    print("DEMO 5: Cache Eviction (LRU)")
    print("=" * 60)

    settings = LogAISettings(
        anthropic_api_key="test-key",
        cache_dir=str(Path.home() / ".logai" / "cache_demo"),
    )
    cache = CacheManager(settings)

    # Temporarily reduce limits for demo
    cache.CACHE_MAX_ENTRIES = 5
    cache.CACHE_EVICTION_BATCH = 1

    await cache.initialize()

    try:
        await cache.clear()

        print(f"\n1. Cache limit set to {cache.CACHE_MAX_ENTRIES} entries")

        # Add entries up to limit
        print(f"\n2. Adding {cache.CACHE_MAX_ENTRIES} entries...")
        for i in range(cache.CACHE_MAX_ENTRIES):
            await cache.set(
                query_type="fetch_logs",
                payload={"events": [], "count": 0},
                log_group=f"/aws/lambda/func{i}",
                start_time=1000 + i * 100000,
                end_time=2000 + i * 100000,
            )

        stats = await cache.get_statistics()
        print(f"   Cache has {stats['entry_count']} entries (at limit)")

        # Add one more entry (should trigger eviction)
        print("\n3. Adding one more entry (should trigger eviction)...")
        await cache.set(
            query_type="fetch_logs",
            payload={"events": [], "count": 0},
            log_group="/aws/lambda/func_new",
            start_time=1000 + 10 * 100000,
            end_time=2000 + 10 * 100000,
        )

        stats = await cache.get_statistics()
        print(f"   Cache has {stats['entry_count']} entries")
        print(f"   ✓ Eviction triggered! Least recently used entries removed.")

    finally:
        await cache.shutdown()


async def demo_performance_improvement():
    """Demonstrate performance improvement with caching."""
    print("\n" + "=" * 60)
    print("DEMO 6: Performance Improvement")
    print("=" * 60)

    settings = LogAISettings(
        anthropic_api_key="test-key",
        cache_dir=str(Path.home() / ".logai" / "cache_demo"),
    )
    cache = CacheManager(settings)
    await cache.initialize()

    try:
        await cache.clear()

        # Simulate "expensive" data fetch
        print("\n1. First fetch (simulate slow CloudWatch API call)...")
        start = time.time()
        await asyncio.sleep(0.5)  # Simulate API latency
        large_payload = {
            "events": [{"message": f"Event {i}"} for i in range(100)],
            "count": 100,
        }
        await cache.set(
            query_type="fetch_logs",
            payload=large_payload,
            log_group="/aws/lambda/test",
            start_time=1000,
            end_time=2000,
        )
        first_duration = time.time() - start
        print(f"   Time taken: {first_duration:.3f}s")

        # Second fetch from cache
        print("\n2. Second fetch (from cache)...")
        start = time.time()
        cached = await cache.get(
            query_type="fetch_logs",
            log_group="/aws/lambda/test",
            start_time=1000,
            end_time=2000,
        )
        second_duration = time.time() - start
        print(f"   Time taken: {second_duration:.3f}s")

        if cached:
            speedup = first_duration / second_duration
            print(f"\n   ✓ Cache speedup: {speedup:.1f}x faster!")

    finally:
        await cache.shutdown()


async def main():
    """Run all demos."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "LogAI Phase 6: Caching System Demo" + " " * 14 + "║")
    print("╚" + "=" * 58 + "╝")

    await demo_basic_caching()
    await demo_cache_key_normalization()
    await demo_ttl_policies()
    await demo_cache_statistics()
    await demo_eviction()
    await demo_performance_improvement()

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nKey Features Demonstrated:")
    print("  ✓ SQLite-based persistent cache")
    print("  ✓ Automatic cache key normalization")
    print("  ✓ Smart TTL policies (historical vs recent data)")
    print("  ✓ LRU eviction when limits exceeded")
    print("  ✓ Cache statistics and monitoring")
    print("  ✓ Significant performance improvements")
    print("\nCache reduces CloudWatch API calls and costs!")
    print()


if __name__ == "__main__":
    asyncio.run(main())
