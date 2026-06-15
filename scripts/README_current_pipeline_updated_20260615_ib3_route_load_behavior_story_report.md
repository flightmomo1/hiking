# README Update — IB3 Route Load Behavior Story Report v1

## Script

scripts/ib3_activity_environment/ib3_route_load_behavior_story_report_v1.py

## Purpose

Generate a story-style HTML report from existing IB3 route-load behavior-response full25 evidence.

## Inputs

- outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_windows.csv
- outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_summary.csv
- outputs/ib3_personal_hiking_features_route_load_comparison_full25_v1/activity_route_load_behavior_response_full25_audit.csv
- outputs/ib3_personal_hiking_features_route_load_comparison_full25_review_v1/activity_route_load_behavior_response_full25_descriptive_review.csv

## Outputs

- outputs/ib3_route_load_behavior_story_report_v1/activity_route_load_behavior_story_report.html
- outputs/ib3_route_load_behavior_story_report_v1/activity_route_load_behavior_story_report_audit.csv

## Method Boundary

The script reads existing evidence only and creates a presentation-oriented report.

It does not:
- recalculate route-load evidence
- modify full25 source CSVs
- generate personal ability score/rank/class
- generate THCI, radar, or final hiking risk score
- infer causality
