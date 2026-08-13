name: root-cleanup
description: Clean up and organize a cluttered root directory with standardized folder structure
version: 1.0.0
author: Hermes Agent
platforms: [linux, macos]
tags: [cleanup, organization, filesystem, maintenance]

# Root Directory Cleanup Skill

Use this skill to clean up and organize a cluttered root directory by creating a standardized folder structure and moving files into appropriate categories.

## When to Use

- When the root directory becomes cluttered with mixed file types
- Before starting new projects to establish clean workspace
- When needing to separate active work from testing/scratch files
- To organize media, documents, and reference materials

## Standard Folder Structure

This skill creates the following organization:

```
/root/
├── projects/          # Active development projects
├── lab/               # Testing scripts, utilities, experiments
├── assets/            # Media, documents, and static files
│   ├── media/         # Audio, video, images
│   ├── documents/     # Text files, HTML, JSON, configs
│   ├── archives/      # Zip, tar.gz, backup files
│   └── imports/       # Windows path artifacts, imports
├── knowledge/         # Reference materials, wikis, brains
�└── archives/          # Completed/old work (alternative to assets/archives)
```

## Implementation Steps

### Phase 1: Assessment
1. Survey current root directory contents
2. Identify active projects, test files, media, documents
3. Note any special considerations (like gbrain memory provider)

### Phase 2: Structure Creation
1. Create standard directory hierarchy:
   - `/root/projects/`
   - `/root/lab/` 
   - `/root/assets/` with subdirs (media, documents, archives, imports)
   - `/root/knowledge/`
   - `/root/archives/`

### Phase 3: File Migration
1. Move active projects to `/root/projects/`
2. Consolidate test scripts and utilities to `/root/lab/`
3. Organize media files to `/root/assets/media/`
4. Move documents to `/root/assets/documents/`
5. Archive compressed files to `/root/assets/archives/`
6. Move reference materials to `/root/knowledge/`
7. Handle special files (Windows paths, symlinks, etc.)

### Phase 4: Special Handling
- **gbrain**: Move to `/root/projects/gbrain` and create symlink `/root/gbrain → /root/projects/gbrain` for Hermes memory provider compatibility
- **Path safety**: Verify no active cron jobs depend on moved files before deletion
- **Environment safety**: Check for hardcoded paths in configurations

### Phase 5: Verification
1. Confirm all expected files are in correct locations
2. Test critical functionality (gbrain CLI, project access)
3. Ensure root contains only essential system/hidden directories plus new structure

## Safety Considerations

- **Symlinks**: Use symlinks for compatibility when moving critical path-dependent tools
- **Backups**: Consider backing up before major moves if uncertainty exists
- **Cron jobs**: Check `.hermes/cron/jobs.json` for dependencies on root paths
- **Environment variables**: Verify PATH and project configs after moves

## Verification Checklist

- [ ] All 8+ active projects moved to `projects/`
- [ ] Test files consolidated in `lab/` (>20 files typical)
- [ ] Media files in `assets/media/`
- [ ] Documents in `assets/documents/`
- [ ] Archives in `assets/archives/` or `/root/archives/`
- [ ] Knowledge materials in `knowledge/`
- [ ] Root directory clean of loose files
- [ ] Critical tools (like gbrain) remain functional

## Customization

Adjust folder names based on specific needs:
- Change `lab` to `scratch` or `experiments` if preferred
- Modify asset categories based on media types
- Add specialized folders like `backups/` or `temp/` as needed

## Example Usage

After invoking this skill, the system will:
1. Create the folder structure
2. Move files methodically by category
3. Provide verification of results
4. Handle special cases like gbrain with symlinks

## Troubleshooting

- **Missing files**: Check `lab/` and `assets/imports/` for misplaced items
- **Broken links**: Verify symlinks point to correct locations
- **Path errors**: Update any hardcoded references in configs or scripts
- **Permission issues**: Ensure proper ownership on moved directories

---
*Skill automatically generated from successful root directory cleanup operation.*