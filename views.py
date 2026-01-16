from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponseBadRequest, HttpResponse
from .models import Novel, Chapter, Category, Comment
from django.db.models import Q


# ---------------------- 基础页面 ----------------------
def novel_list(request):
    """小说列表页"""
    # 获取分类筛选条件
    category_id = request.GET.get('category', '')
    # 获取搜索关键词
    keyword = request.GET.get('keyword', '')

    # 基础查询：仅展示审核通过的小说
    novels = Novel.objects.filter(is_approved=True)

    # 分类筛选
    if category_id and category_id.isdigit():
        novels = novels.filter(category_id=int(category_id))

    # 关键词搜索（标题/作者）
    if keyword:
        novels = novels.filter(
            Q(title__icontains=keyword) | Q(author__icontains=keyword)
        )

    # 获取所有分类（用于筛选下拉框）
    categories = Category.objects.all()

    context = {
        'novels': novels,
        'categories': categories,
        'selected_category': category_id,
        'keyword': keyword
    }
    return render(request, 'novel/novel_list.html', context)


# ---------------------- 用户认证 ----------------------
def login_view(request):
    """用户登录"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            # 跳转到登录前的页面，若无则跳转到首页
            next_url = request.GET.get('next', '/novel/')
            return redirect(next_url)
        else:
            messages.error(request, '用户名或密码错误！')

    return render(request, 'novel/login.html')


def logout_view(request):
    """用户退出"""
    logout(request)
    messages.success(request, '已成功退出！')
    return redirect('novel:login')


def register_view(request):
    """用户注册"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '注册成功！请登录')
            return redirect('novel:login')
    else:
        form = UserCreationForm()

    return render(request, 'novel/register.html', {'form': form})


# ---------------------- 小说管理 ----------------------
@login_required
def add_novel(request):
    """添加小说"""
    if request.method == 'POST':
        title = request.POST.get('title')
        author = request.POST.get('author')
        category_id = request.POST.get('category')
        intro = request.POST.get('intro', '')

        # 基础校验
        if not title or not author or not category_id:
            categories = Category.objects.all()
            return render(request, 'novel/add_novel.html', {
                'error': '标题、作者、分类不能为空！',
                'categories': categories
            })

        # 获取分类
        category = get_object_or_404(Category, id=category_id)

        # 创建小说（默认未审核）
        novel = Novel.objects.create(
            title=title,
            author=author,
            category=category,
            intro=intro,
            uploader=request.user,
            is_approved=False
        )

        messages.success(request, '小说创建成功！请添加章节')
        return redirect('novel:chapter_list', novel_id=novel.id)

    # GET请求：展示添加表单
    categories = Category.objects.all()
    return render(request, 'novel/add_novel.html', {'categories': categories})


@login_required
def edit_novel(request, novel_id):
    """编辑小说"""
    novel = get_object_or_404(Novel, id=novel_id)

    # 权限校验：仅上传者可编辑
    if novel.uploader != request.user and not request.user.is_superuser:
        return HttpResponseForbidden('你没有权限编辑该小说！')

    if request.method == 'POST':
        title = request.POST.get('title')
        author = request.POST.get('author')
        category_id = request.POST.get('category')
        intro = request.POST.get('intro', '')

        # 基础校验
        if not title or not author or not category_id:
            categories = Category.objects.all()
            return render(request, 'novel/edit_novel.html', {
                'error': '标题、作者、分类不能为空！',
                'novel': novel,
                'categories': categories
            })

        # 更新小说信息
        category = get_object_or_404(Category, id=category_id)
        novel.title = title
        novel.author = author
        novel.category = category
        novel.intro = intro
        novel.save()

        messages.success(request, '小说信息修改成功！')
        return redirect('novel:chapter_list', novel_id=novel.id)

    # GET请求：展示编辑表单
    categories = Category.objects.all()
    return render(request, 'novel/edit_novel.html', {
        'novel': novel,
        'categories': categories
    })


@login_required
def delete_novel(request, novel_id):
    """删除小说"""
    novel = get_object_or_404(Novel, id=novel_id)

    # 权限校验：仅上传者/超级管理员可删除
    if novel.uploader != request.user and not request.user.is_superuser:
        return HttpResponseForbidden('你没有权限删除该小说！')

    novel.delete()
    messages.success(request, '小说已删除！')
    return redirect('novel:novel_list')


# ---------------------- 章节管理 ----------------------
@login_required
def chapter_list(request, novel_id):
    """章节列表"""
    novel = get_object_or_404(Novel, id=novel_id)

    # 权限校验：仅上传者/超级管理员可查看未审核章节
    if novel.uploader != request.user and not request.user.is_superuser:
        chapters = novel.chapters.filter(is_approved=True)
    else:
        chapters = novel.chapters.all()

    context = {
        'novel': novel,
        'chapters': chapters
    }
    return render(request, 'novel/chapter_list.html', context)


@login_required
def add_chapter(request, novel_id):
    """添加章节"""
    novel = get_object_or_404(Novel, id=novel_id)

    # 权限校验：仅上传者可添加
    if novel.uploader != request.user:
        return HttpResponseForbidden('你没有权限为该小说添加章节！')

    # 获取已有排序号
    existing_sort_nums = Chapter.objects.filter(novel=novel).values_list('sort_num', flat=True)
    next_sort_num = max(existing_sort_nums) + 1 if existing_sort_nums else 1

    if request.method == 'POST':
        title = request.POST.get('title')
        sort_num = request.POST.get('sort_num')
        content = request.POST.get('content')

        # 基础校验
        if not title or not sort_num or not content:
            return render(request, 'novel/add_chapter.html', {
                'novel': novel,
                'error': '标题、排序号、内容均不能为空！',
                'existing_sort_nums': existing_sort_nums,
                'next_sort_num': next_sort_num
            })

        # 转换排序号
        try:
            sort_num = int(sort_num)
        except ValueError:
            return render(request, 'novel/add_chapter.html', {
                'novel': novel,
                'error': '排序号必须是整数！',
                'existing_sort_nums': existing_sort_nums,
                'next_sort_num': next_sort_num
            })

        # 校验排序号是否重复
        if Chapter.objects.filter(novel=novel, sort_num=sort_num).exists():
            return render(request, 'novel/add_chapter.html', {
                'novel': novel,
                'error': f'排序号 {sort_num} 已存在！该小说已有排序号：{sorted(existing_sort_nums)}',
                'existing_sort_nums': existing_sort_nums,
                'next_sort_num': next_sort_num
            })

        # 创建章节
        Chapter.objects.create(
            novel=novel,
            title=title,
            sort_num=sort_num,
            content=content,
            uploader=request.user,
            is_approved=False
        )
        return redirect('novel:chapter_list', novel_id=novel.id)

    # GET请求
    return render(request, 'novel/add_chapter.html', {
        'novel': novel,
        'existing_sort_nums': existing_sort_nums,
        'next_sort_num': next_sort_num
    })


@login_required
def edit_chapter(request, chapter_id):
    """编辑章节"""
    chapter = get_object_or_404(Chapter, id=chapter_id)

    # 权限校验
    if chapter.uploader != request.user and not request.user.is_superuser:
        return HttpResponseForbidden('你没有权限编辑该章节！')

    if request.method == 'POST':
        title = request.POST.get('title')
        sort_num = request.POST.get('sort_num')
        content = request.POST.get('content')

        # 基础校验
        if not title or not sort_num or not content:
            return render(request, 'novel/edit_chapter.html', {
                'chapter': chapter,
                'error': '标题、排序号、内容均不能为空！'
            })

        # 转换排序号
        try:
            sort_num = int(sort_num)
        except ValueError:
            return render(request, 'novel/edit_chapter.html', {
                'chapter': chapter,
                'error': '排序号必须是整数！'
            })

        # 校验排序号是否重复（排除自身）
        if Chapter.objects.filter(
                novel=chapter.novel,
                sort_num=sort_num
        ).exclude(id=chapter.id).exists():
            return render(request, 'novel/edit_chapter.html', {
                'chapter': chapter,
                'error': f'排序号 {sort_num} 已存在！'
            })

        # 更新章节
        chapter.title = title
        chapter.sort_num = sort_num
        chapter.content = content
        chapter.is_approved = False  # 修改后重置为未审核
        chapter.save()

        messages.success(request, '章节修改成功！需管理员重新审核')
        return redirect('novel:chapter_detail', chapter_id=chapter.id)

    # GET请求
    return render(request, 'novel/edit_chapter.html', {'chapter': chapter})


@login_required
def delete_chapter(request, chapter_id):
    """删除章节"""
    chapter = get_object_or_404(Chapter, id=chapter_id)
    novel_id = chapter.novel.id

    # 权限校验
    if chapter.uploader != request.user and not request.user.is_superuser:
        return HttpResponseForbidden('你没有权限删除该章节！')

    chapter.delete()
    messages.success(request, '章节已删除！')
    return redirect('novel:chapter_list', novel_id=novel_id)


def chapter_detail(request, chapter_id):
    """章节详情（修复重复传参问题+权限控制：管理员/作者可查看待审核章节）"""
    # 第一步：查询章节是否存在（不先过滤审核状态）
    chapter = get_object_or_404(Chapter, id=chapter_id)

    # 第二步：权限判断，控制是否能查看该章节
    user = request.user
    can_view = False

    # 超级管理员或章节作者可查看（无论是否审核）
    if user.is_authenticated:
        if user.is_superuser or chapter.uploader == user:
            can_view = True

    # 普通用户/未登录用户仅能查看已审核章节
    if chapter.is_approved:
        can_view = True

    # 无权查看则返回404
    if not can_view:
        raise Http404("该章节不存在或你无权查看")

    # 第三步：查询该章节的有效评论
    comments = chapter.comments.filter(is_approved=True)

    # 第四步：后端处理章节内容换行分割（修复模板语法错误）
    chapter_paragraphs = []
    if chapter.content:
        raw_paragraphs = chapter.content.split('\n')
        for para in raw_paragraphs:
            stripped_para = para.strip()
            if stripped_para:
                chapter_paragraphs.append(stripped_para)

    # 第五步：构建上下章查询过滤条件（避免重复novel参数）
    chapter_filter = {
        'novel': chapter.novel,  # 仅在这里定义novel参数
    }
    # 普通用户仅查询已审核章节；管理员/作者查询所有章节（不添加is_approved过滤）
    if not can_view:  # 仅当用户无权查看待审核章节时，添加审核过滤
        chapter_filter['is_approved'] = True

    # 第六步：查询上下章（仅通过**chapter_filter传递参数，无重复）
    # 上一章：排序号小于当前章节，按排序号倒序取第一个
    prev_chapter = Chapter.objects.filter(
        sort_num__lt=chapter.sort_num,
        **chapter_filter  # 解包字典，包含novel（可选：is_approved）
    ).order_by('-sort_num').first()

    # 下一章：排序号大于当前章节，按排序号正序取第一个
    next_chapter = Chapter.objects.filter(
        sort_num__gt=chapter.sort_num,
        **chapter_filter  # 解包字典，包含novel（可选：is_approved）
    ).order_by('sort_num').first()

    # 传递模板数据
    context = {
        'chapter': chapter,
        'novel': chapter.novel,
        'comments': comments,
        'next_chapter': next_chapter,
        'prev_chapter': prev_chapter,
        'chapter_paragraphs': chapter_paragraphs,
    }

    return render(request, 'novel/chapter_detail.html', context)


# ---------------------- 评论功能（新增） ----------------------
@login_required
def add_comment(request, chapter_id):
    """提交评论（兼容待审核章节，保留核心校验逻辑）"""
    # 移除 is_approved=True 过滤，允许对自己的待审核章节评论
    chapter = get_object_or_404(Chapter, id=chapter_id)

    # 可选：增加权限校验（仅允许章节作者/超级管理员/所有登录用户评论，按需开启）
    # user = request.user
    # if not (user.is_superuser or chapter.uploader == user):
    #     messages.error(request, "你无权对该章节发表评论！")
    #     return redirect('novel:chapter_detail', chapter_id=chapter_id)

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()

        # 1. 内容非空校验
        if not content:
            messages.error(request, '评论内容不能为空！')
            return redirect('novel:chapter_detail', chapter_id=chapter_id)
        # 2. 字数限制校验（500字以内）
        if len(content) > 500:
            messages.error(request, '评论内容不能超过500字！')
            return redirect('novel:chapter_detail', chapter_id=chapter_id)

        # 3. 创建评论（若你的 Comment 模型 is_approved 默认是 False，需管理员审核后显示；若默认 True，立即显示）
        Comment.objects.create(
            chapter=chapter,
            user=request.user,
            content=content
            # 若需手动指定审核状态，可添加：is_approved=True（立即显示） / is_approved=False（待审核）
        )
        messages.success(request, '评论发表成功！')
        return redirect('novel:chapter_detail', chapter_id=chapter_id)

    # GET 请求直接重定向到章节详情页（避免直接访问评论提交接口）
    return redirect('novel:chapter_detail', chapter_id=chapter_id)


@login_required
def delete_comment(request, comment_id):
    """删除评论"""
    comment = get_object_or_404(Comment, id=comment_id)

    # 权限校验
    if comment.user != request.user and not request.user.is_superuser:
        return HttpResponseForbidden('你没有权限删除该评论！')

    chapter_id = comment.chapter.id
    comment.delete()
    messages.success(request, '评论已删除！')
    return redirect('novel:chapter_detail', chapter_id=chapter_id)


# ---------------------- 管理员审核 ----------------------
@login_required
def approve_novel(request, novel_id):
    """审核小说（仅超级管理员）"""
    if not request.user.is_superuser:
        return HttpResponseForbidden('仅管理员可审核小说！')

    novel = get_object_or_404(Novel, id=novel_id)
    novel.is_approved = True
    novel.save()
    messages.success(request, '小说审核通过！')
    return redirect('novel:novel_list')


@login_required
def approve_chapter(request, chapter_id):
    """审核章节（仅超级管理员）"""
    if not request.user.is_superuser:
        return HttpResponseForbidden('仅管理员可审核章节！')

    chapter = get_object_or_404(Chapter, id=chapter_id)
    chapter.is_approved = True
    chapter.save()
    messages.success(request, '章节审核通过！')
    return redirect('novel:chapter_list', novel_id=chapter.novel.id)