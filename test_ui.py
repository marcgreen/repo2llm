import pytest
from playwright.sync_api import expect

playwright_tests = pytest.mark.playwright

@playwright_tests
def test_directory_structure_toggle(loaded_ui_test_repo_page):
    page = loaded_ui_test_repo_page
    
    toggles = page.locator(".toggle")
    
    for i in range(toggles.count()):
        toggle = toggles.nth(i)
        parent = toggle.locator("xpath=..")
        children = parent.locator("xpath=./ul/li")
        
        if children.count() > 0:
            expect(children).to_have_css("display", "none")
            
            toggle.click()
            expect(children).not_to_have_css("display", "none")
            
            toggle.click()
            expect(children).to_have_css("display", "none")
    
    if toggles.count() > 1:
        parent_toggle = toggles.first
        parent_toggle.click()
        
        child_toggle = parent_toggle.locator("xpath=../ul/li").locator(".toggle").first
        if child_toggle.count() > 0:
            child_toggle.click()
            grandchild = child_toggle.locator("xpath=../ul/li").first
            
            expect(grandchild).not_to_have_css("display", "none")
            
            parent_toggle.click()
            parent_toggle.click()
            expect(grandchild).to_have_css("display", "none")

@playwright_tests
def test_select_all_visual_update(loaded_ui_test_repo_page):
    page = loaded_ui_test_repo_page
    
    checkboxes = page.locator("input[name='selected_files']")
    total_checkboxes = checkboxes.count()
    
    if total_checkboxes == 0:
        pytest.skip("No files to select")
    
    page.click("button:has-text('Select All')")
    expect(checkboxes).to_have_count(total_checkboxes)
    for checkbox in checkboxes.all():
        expect(checkbox).to_be_checked()
    
    expect(page.locator("#totals")).not_to_have_text("Total: 0 files")
    
    page.click("button:has-text('Unselect All')")
    for checkbox in checkboxes.all():
        expect(checkbox).not_to_be_checked()
    
    expect(page.locator("#totals")).to_have_text("Total: 0 files, 0 bytes, 0 tokens")
    
    if total_checkboxes > 1:
        page.click("button:has-text('Select All')")
        checkboxes.first.uncheck()
        expect(checkboxes.first).not_to_be_checked()
        expect(checkboxes.nth(1)).to_be_checked()
        
        new_total = page.locator("#totals").inner_text()
        assert new_total != "Total: 0 files, 0 bytes, 0 tokens"
        assert new_total != f"Total: {total_checkboxes} files"

@playwright_tests
def test_file_type_exclusion_visual_feedback(loaded_ui_test_repo_page):
    page = loaded_ui_test_repo_page
    
    page.click("button:has-text('Select All')")
    
    file_type_checkboxes = page.locator("input[name='file_types']")
    
    for i in range(file_type_checkboxes.count()):
        file_type_checkbox = file_type_checkboxes.nth(i)
        
        file_type_checkbox.check()
        
        excluded_files = page.locator(f"input[name='selected_files'][disabled]")
        for file in excluded_files.all():
            expect(file).to_be_disabled()
            expect(file.locator("..")).to_have_css("opacity", "0.5")
        
        included_files = page.locator(f"input[name='selected_files']:not([disabled])")
        for file in included_files.all():
            expect(file).to_be_enabled()
            expect(file.locator("..")).not_to_have_css("opacity", "0.5")
        
        total_files = page.locator("input[name='selected_files']").count()
        current_total = int(page.locator("#totals").inner_text().split()[1])
        assert current_total <= total_files
        
        file_type_checkbox.uncheck()
        expect(page.locator(f"input[name='selected_files'][disabled]")).to_have_count(0)
    
    if file_type_checkboxes.count() >= 2:
        file_type_checkboxes.first.check()
        file_type_checkboxes.nth(1).check()
        
        excluded_count = page.locator("input[name='selected_files'][disabled]").count()
        total_count = page.locator("input[name='selected_files']").count()
        
        assert excluded_count > 0 and excluded_count < total_count
        
        total_text = page.locator("#totals").inner_text()
        assert int(total_text.split()[1]) == total_count - excluded_count
    
    for checkbox in file_type_checkboxes.all():
        checkbox.check()
    
    select_all_button = page.locator("button:has-text('Select All')")
    expect(select_all_button).to_be_disabled()