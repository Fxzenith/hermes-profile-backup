# Root Directory Cleanup Plan

**Goal:** Clean up and organize a cluttered `/root` directory by creating a standardized folder structure and migrating files into appropriate categories while maintaining Hermes compatibility.

**Architecture:** This plan creates a systematic cleanup workflow that identifies file types, creates standardized directories (`projects/`, `lab/`, `assets/`, `knowledge/`, `archives/`), migrates files by category, and establishes symlinks for path-dependent tools like gbrain. The workflow is idempotent and can be re-run safely.

**Tech Stack:** Linux shell commands (mkdir, mv, ln), gbrain memory provider, Hermes profile awareness

---
```

# Root Directory Cleanup Implementation Plan

## Phase 1: Assessment & Inventory

### Task 1.1: Survey Current Root Contents
**Objective:** Document all files and directories in `/root` to understand what needs organizing.

**Files to inspect:**
- Read `/root` directory listing

**Step 1:** Run `ls -la /root` to get full listing including hidden files

**Step 2:** Catalog findings into categories:
- Active projects
- Test scripts and utilities
- Media files (images, audio, video)
- Documents and configs
- Archive/backup files
- Windows path artifacts
- System/hidden directories

**Expected output:** Comprehensive inventory of ~100+ items across root

### Task 1.2: Identify Path-Dependent Tools
**Objective:** Find tools that rely on specific root paths (especially gbrain).

**Files to check:**
- `.hermes/plugins/gbrain/` configuration
- Environment variables referencing root paths
- Scripts with hardcoded `/root/...` paths

**Step 1:** Check `GBRAIN_DIR` env var and gbrain config

**Step 2:** Identify all scripts referencing `/root/gbrain` or similar paths

**Step 3:** Document dependencies before any moves

---

## Phase 2: Structure Creation

### Task 2.1: Create Standard Directory Hierarchy
**Objective:** Establish the organizational framework.

**Create these directories:**
- `/root/projects/` - Active development projects
- `/root/lab/` - Test scripts, utilities, experiments
- `/root/assets/media/` - Audio, video, images
- `/root/assets/documents/` - Text files, configs, docs
- `/root/assets/archives/` - Zip, tar.gz, backups
- `/root/assets/imports/` - Windows path artifacts, imports
- `/root/knowledge/` - Reference materials, wikis, journals
- `/root/archives/` - Completed/old work (alternative structure)

**Step 1:** Run `mkdir -p /root/projects /root/lab /root/assets/media /root/assets/documents /root/assets/archives /root/assets/imports /root/knowledge /root/archives`

**Step 2:** Verify all directories created

### Task 2.2: Establish GBrain Symlink
**Objective:** Maintain Hermes memory provider compatibility.

**Create symlink:**
- `/root/gbrain → /root/projects/gbrain`

**Step 1:** Move actual gbrain data to `/root/projects/gbrain` if not already there

**Step 2:** Create symlink `ln -sf /root/projects/gbrain /root/gbrain`

**Step 3:** Verify gbrain CLI still works via the symlink

---

## Phase 3: File Migration

### Task 3.1: Move Active Projects
**Objective:** Consolidate active projects into `projects/`.

**Projects to move (8 total):**
- Agent-Reach
- ContentRepurposeSystem-main
- Instagram daily auto-post
- autoclipping
- gbrain
- hermes-profile-backup
- saas-leads-pipeline
- video-use

**Step 1:** For each project, run `mv /root/<project> /root/projects/`

**Step 2:** Verify each project moved successfully

**Step 3:** Create symlinks if needed for backward compatibility

### Task 3.2: Consolidate Test Scripts & Utilities
**Objective:** Move 51+ test/utility files to `lab/`.

**Files to consolidate:**
- `test_*.py` files
- `verify_*.ts` files  
- `minimal-*.tldr` files
- `*.excalidraw` visual artifacts
- Other test/scratch files

**Step 1:** Run `mv /root/test_*.py /root/lab/`

**Step 2:** Run `mv /root/verify_*.ts /root/lab/`

**Step 3:** Run `mv /root/minimal-*.tldr /root/lab/`

**Step 4:** Run `mv /root/*.excalidraw /root/lab/`

**Step 5:** Run `mv /root/other-test-files /root/lab/`

**Step 6:** Verify consolidation in `/root/lab/`

### Task 3.3: Organize Media Files
**Objective:** Sort media into appropriate asset subdirectories.

**Media categories:**
- Images → `/root/assets/media/`
- Audio → `/root/assets/media/`
- Video → `/root/assets/media/`

**Step 1:** Run `mv /root/*.png /root/assets/media/`

**Step 2:** Run `mv /root/*.jpg /root/assets/media/`

**Step 3:** Run `mv /root/*.webp /root/assets/media/`

**Step 4:** Run `mv /root/*.mp3 /root/assets/media/`

**Step 5:** Run `mv /root/*.mp4 /root/assets/media/`

**Step 6:** Verify media organized

### Task 3.4: Move Documents & Configs
**Objective:** Organize documents into `assets/documents/`.

**Files:**
- Configuration files
- Log files (Herme, cron, etc.)
- JSON/CSV config files
- Script docs

**Step 1:** Run `mv /root/*.json /root/assets/documents/`

**Step 2:** Run `mv /root/*.yaml /root/assets/documents/`

**Step 3:** Run `mv /root/*.yml /root/assets/documents/`

**Step 4:** Run `mv /root/*.md /root/assets/documents/`

**Step 5:** Run `mv /root/.hermes/logs/ /root/assets/documents/` (or keep structure)

### Task 3.5: Archive Compressed Files
**Objective:** Move archive files to `assets/archives/`.

**Files:**
- `.zip` files
- `.tar.gz` files
- `.tar` files

**Step 1:** Run `mv /root/*.zip /root/assets/archives/`

**Step 2:** Run `mv /root/*.tar.gz /root/assets/archives/`

**Step 3:** Run `mv /root/*.tar /root/assets/archives/`

### Task 3.6: Move Windows Path Artifacts
**Objective:** Safely handle Windows-style path files.

**Files:**
- Windows path files (detected during inventory)

**Step 1:** Move to `/root/assets/imports/`

**Step 2:** Create documentation on safe handling

### Task 3.7: Move Knowledge Artifacts
**Objective:** Organize knowledge bases to `knowledge/`.

**Artifacts to move:**
- `brain` directory/second brain data
- `brain-content` 
- `JFX JOURNAL`
- `SOUL.md`
- `wiki` contents

**Step 1:** Run `mv /root/brain /root/knowledge/`

**Step 2:** Run `mv /root/brain-content /root/knowledge/`

**Step 3:** Run `mv /root/JFX* /root/knowledge/`

**Step 4:** Run `mv /root/SOUL.md /root/knowledge/`

**Step 5:** Run `mv /root/wiki /root/knowledge/`

### Task 3.8: Final Verification & Cleanup
**Objective:** Ensure root is clean and everything is in correct location.

**Verification steps:**
1. Run `ls -la /root` - should show only essential dirs + new structure
2. Check no loose files remain in `/root` root
3. Verify all projects accessible from `/root/projects/`
4. Verify gbrain works via symlink
5. Check lab has test files
6. Check assets are organized
7. Check knowledge is in place

**Step 1:** Comprehensive root listing

**Step 2:** Test critical functionality

**Step 3:** Document any remaining items

---

## Phase 4: Post-Cleanup

### Task 4.1: Save Cleanup as Reusable Skill
**Objective:** Make this cleanup process reusable.

**Create skill:** `root-cleanup` at `/root/.hermes/skills/root-cleanup/SKILL.md`

**Content includes:**
- Standard folder structure documentation
- Step-by-step implementation
- Safety considerations
- Verification checklist
- Customization options

### Task 4.2: Update Hermes Configuration
**Objective:** Ensure Hermes works with new structure.

**Checks:**
- Verify `.hermes/plugins/gbrain/` still references correct paths
- Check any config files pointing to root directories
- Update environment variables if needed

### Task 4.3: Document the Organization
**Objective:** Create reference for future cleanup.

**Document:**
- What went where
- Symlink locations
- Any broken references to fix

---

## Verification Checklist

- [ ] All 8+ active projects moved to `/root/projects/`
- [ ] Test files consolidated in `/root/lab/` (>20 files typical)
- [ ] Media files in `/root/assets/media/`
- [ ] Documents in `/root/assets/documents/`
- [ ] Archives in `/root/assets/archives/`
- [ ] Windows artifacts in `/root/assets/imports/`
- [ ] Knowledge materials in `/root/knowledge/`
- [ ] Root directory clean of loose files (only essential system dirs remain)
- [ ] Critical tools (like gbrain) remain functional via symlinks
- [ ] Skill `root-cleanup` saved and documented

---